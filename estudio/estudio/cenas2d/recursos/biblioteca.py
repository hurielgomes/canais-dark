"""
biblioteca.py - biblioteca de recursos reutilizaveis (personagens, objetos, cenarios) + fluxo de aprovacao.

    bib = Biblioteca("biblioteca/", aprovacao="auto")          # "auto" = producao em massa; "manual" = pendente ate aprovar
    r = bib.registrar("tigre.json")                            # novo | reutilizado | nova_versao   (dedupe por hash)
    rig = bib.rig("tigre")                                     # recurso pronto para animar (cache)
    bib.aprovar("tigre") / bib.rejeitar("tigre", "motivo")
    bib.galeria("galeria.html", usados=bib.usos)               # pagina estatica com previas, status NOVO/REUTILIZADO

Estrutura em disco:  raiz/index.json  +  raiz/recursos/<tipo>/<id>.v<N>.json (+ .svg original quando houver).
"""
import base64
import hashlib
import io
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw

from ..rig import Rig, camadas_cenario
from .svg import importar_svg
from .validar import RecursoInvalido, validar_recurso


def _canon(rec):
    return json.dumps(rec, sort_keys=True, default=list, ensure_ascii=False)


def hash_recurso(rec):
    r = dict(rec)
    for k in ("versao", "id", "nome", "tags"):          # o hash identifica o DESENHO, nao o nome (evita duplicatas com outro id)
        r.pop(k, None)
    return hashlib.sha1(_canon(r).encode("utf-8")).hexdigest()[:16]


class Resultado:
    def __init__(self, id, estado, avisos=None, status=None):
        self.id, self.estado, self.avisos, self.status = id, estado, avisos or [], status

    def __repr__(self):
        return f"<{self.id}: {self.estado} ({self.status})>"


class Biblioteca:
    def __init__(self, raiz, aprovacao="auto", bloquear_pendentes=False):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.aprovacao = aprovacao
        self.bloquear = bloquear_pendentes
        self.f_index = self.raiz / "index.json"
        self.idx = json.loads(self.f_index.read_text(encoding="utf-8")) if self.f_index.exists() else {"recursos": {}}
        self._rigs = {}
        self.usos = {}          # id -> {"estado": novo|reutilizado|nova_versao, "status": ...}  (so o que foi USADO)
        self._reg = {}          # id -> estado do registro nesta execucao
        self.problemas = []     # mensagens de erro/aviso da execucao

    # ------------------------------------------------------------------ persistencia
    def _salvar_index(self):
        self.f_index.write_text(json.dumps(self.idx, indent=1, ensure_ascii=False), encoding="utf-8")

    def listar(self, status=None):
        return [dict(id=i, **e) for i, e in sorted(self.idx["recursos"].items()) if status in (None, e["status"])]

    # ------------------------------------------------------------------ registro
    def _ler_origem(self, origem, id, tipo, sidecar):
        avisos = []
        if isinstance(origem, dict):
            return dict(origem), avisos, None
        p = Path(origem)
        if p.suffix.lower() == ".svg":
            rid = id or p.stem
            sc = sidecar
            if sc is None:
                for cand in (p.with_suffix(".anim.json"), p.with_suffix(".json")):
                    if cand.exists():
                        sc = json.loads(cand.read_text(encoding="utf-8"))
                        break
            rec, av = importar_svg(p.read_bytes(), rid, tipo or "objeto", sc)
            return rec, av, p.read_text(encoding="utf-8", errors="replace")
        d = json.loads(p.read_text(encoding="utf-8"))
        return d, avisos, None

    def registrar(self, origem, id=None, tipo=None, tags=None, sidecar=None):
        """valida e guarda. NUNCA executa codigo. Levanta RecursoInvalido se o recurso for invalido."""
        d, avisos, svg_txt = self._ler_origem(origem, id, tipo, sidecar)
        if id:
            d["id"] = id
        if tipo and "tipo" not in d:
            d["tipo"] = tipo
        rec, av2 = validar_recurso(d)
        avisos += av2
        rid, h = rec["id"], hash_recurso(rec)
        ents = self.idx["recursos"]
        # mesmo conteudo ja existe (com qualquer id)?
        for eid, e in ents.items():
            if e["hash"] == h and e["status"] != "rejeitado":
                self._reg.setdefault(eid, "reutilizado")
                return Resultado(eid, "reutilizado", avisos, e["status"])
        versao = 1
        estado = "novo"
        if rid in ents:
            versao = ents[rid]["versao"] + 1
            estado = "nova_versao"
        rec["versao"] = versao
        status = "aprovado" if self.aprovacao == "auto" else "pendente"
        sub = self.raiz / "recursos" / rec["tipo"]
        sub.mkdir(parents=True, exist_ok=True)
        arq = sub / f"{rid}.v{versao}.json"
        arq.write_text(json.dumps(d, indent=1, ensure_ascii=False, default=list), encoding="utf-8")
        if svg_txt:
            (sub / f"{rid}.v{versao}.svg").write_text(svg_txt, encoding="utf-8")
        ents[rid] = {"arquivo": str(arq.relative_to(self.raiz)), "tipo": rec["tipo"], "hash": h, "versao": versao, "status": status,
                     "tags": rec["tags"], "nome": rec["nome"], "criado": time.strftime("%Y-%m-%d %H:%M"),
                     "animacoes": sorted(rec["animacoes"]), "motivo": ""}
        self._salvar_index()
        self._rigs.pop(rid, None)
        self._reg[rid] = estado
        return Resultado(rid, estado, avisos, status)

    def registrar_pasta(self, pasta):
        """registra todos os .json/.svg de uma pasta (ignora *.anim.json de apoio e index)"""
        out = []
        for p in sorted(Path(pasta).glob("*")):
            if p.suffix.lower() == ".svg" or (p.suffix.lower() == ".json" and not p.name.endswith(".anim.json") and p.name != "index.json"):
                if p.suffix.lower() == ".json" and p.with_suffix(".svg").exists():
                    continue
                try:
                    out.append(self.registrar(p))
                except (RecursoInvalido, ValueError, OSError) as e:
                    self.problemas.append(f"{p.name}: {e}")
        return out

    # ------------------------------------------------------------------ uso
    def obter(self, ref):
        e = self.idx["recursos"].get(ref)
        if not e:
            raise KeyError(f"recurso '{ref}' nao existe na biblioteca")
        if e["status"] == "rejeitado":
            raise RecursoInvalido(f"recurso '{ref}' foi rejeitado ({e.get('motivo', '')})")
        if e["status"] == "pendente" and self.bloquear:
            raise RecursoInvalido(f"recurso '{ref}' aguarda aprovacao")
        d = json.loads((self.raiz / e["arquivo"]).read_text(encoding="utf-8"))
        svg = (self.raiz / e["arquivo"]).with_suffix(".svg")
        if svg.exists():               # recurso importado de SVG: reconverte (determinístico)
            sc = None
            for cand in (svg.with_suffix(".anim.json"),):
                if cand.exists():
                    sc = json.loads(cand.read_text(encoding="utf-8"))
        rec, _ = validar_recurso(d if "partes" in d or "camadas" in d else d)
        return rec, e

    def rig(self, ref):
        if ref not in self._rigs:
            rec, e = self.obter(ref)
            self._rigs[ref] = Rig(rec)
            self.usos.setdefault(ref, {"estado": self._reg.get(ref, "reutilizado"), "status": e["status"]})
        return self._rigs[ref]

    def aprovar(self, ref):
        self.idx["recursos"][ref]["status"] = "aprovado"
        self._salvar_index()

    def rejeitar(self, ref, motivo=""):
        self.idx["recursos"][ref].update(status="rejeitado", motivo=motivo)
        self._salvar_index()

    def pendentes(self):
        return [r["id"] for r in self.listar("pendente")]

    # ------------------------------------------------------------------ previa / galeria
    def previa(self, ref, alt=210):
        """imagem PNG (PIL) com a previa do recurso: poses de cada animacao (ou camadas do cenario)"""
        rig = self.rig(ref)
        rec = rig.rec
        if rec["tipo"] == "cenario":
            W, H = 560, 315
            esc = H / max(1.0, (rec["caixa"][3] - rec["caixa"][1]))
            foco = ((rec["caixa"][0] + rec["caixa"][2]) / 2, (rec["caixa"][1] + rec["caixa"][3]) / 2)
            base = Image.new("RGBA", (W, H), (12, 12, 20, 255))
            from ..rig import Posicionado
            for k, _, img, x, y in sorted(camadas_cenario(rig, W, H, esc, foco), key=lambda t: t[0]):
                Posicionado._cola(base, img, x, y)
            return base.convert("RGB")
        quadros, legendas = [], []
        casos = [("pose base", None, 0.0)]
        for nome in rig.capacidades()[:5]:
            d = rig.duracao(nome)
            for f in (0.0, 0.33, 0.66):
                casos.append((nome, nome, d * f))
        c0, c1, c2, c3 = rec["caixa"]
        s = alt / max(1.0, (c3 - c1))
        for rot, nome, t in casos:
            pose = rig.pose_final([(rig.pose_de(nome, t), 1.0)]) if nome else rig.pose_final([])
            wpx, hpx = int((c2 - c0) * s) + 40, int((c3 - c1) * s) + 40
            pos = rig.posicionar(pose, s, False, (20 + (rec["base"][0] - c0) * s, 20 + (rec["base"][1] - c1) * s))
            res = pos.desenhar(limite=(0, 0, wpx, hpx))
            cel = Image.new("RGB", (wpx, hpx), (28, 32, 48))
            if res:
                img, ox, oy = res
                cel.paste(img, (ox, oy), img)
            quadros.append((rot, cel))
        # monta tira (max 8 por linha)
        cw = max(q[1].width for q in quadros)
        ch = max(q[1].height for q in quadros)
        cols = min(8, len(quadros))
        rows = (len(quadros) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cw, rows * (ch + 18)), (20, 22, 34))
        dr = ImageDraw.Draw(sheet)
        for i, (rot, cel) in enumerate(quadros):
            x, y = (i % cols) * cw, (i // cols) * (ch + 18)
            sheet.paste(cel, (x, y + 18))
            dr.text((x + 6, y + 3), rot, fill=(200, 210, 240))
        return sheet

    def galeria(self, caminho_html, usados=None):
        usados = usados if usados is not None else self.usos
        linhas = []
        for ref in sorted(usados):
            e = self.idx["recursos"].get(ref)
            if not e:
                continue
            try:
                buf = io.BytesIO()
                self.previa(ref).save(buf, "PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
            except Exception as ex:      # previa nunca derruba o fluxo
                b64 = ""
                self.problemas.append(f"previa de '{ref}' falhou: {ex}")
            est = usados[ref]["estado"]
            cor_est = {"novo": "#e0a030", "nova_versao": "#c080ff", "reutilizado": "#40b080"}.get(est, "#888")
            cor_st = {"aprovado": "#40b080", "pendente": "#e0a030", "rejeitado": "#e05050"}.get(e["status"], "#888")
            linhas.append(f"""<section><h3>{e['nome']} <small>({ref} v{e['versao']} · {e['tipo']})</small>
<span style="background:{cor_est}">{est.upper().replace('_', ' ')}</span> <span style="background:{cor_st}">{e['status'].upper()}</span></h3>
<img src="data:image/png;base64,{b64}"><p>animacoes: {', '.join(e['animacoes']) or '-'} · tags: {', '.join(e['tags']) or '-'}</p>
<code>python m1_recursos.py aprovar {ref} &nbsp;|&nbsp; python m1_recursos.py rejeitar {ref} "motivo"</code></section>""")
        html = f"""<!doctype html><meta charset="utf-8"><title>Recursos do projeto</title>
<style>body{{font:14px system-ui;background:#10121c;color:#dfe5ff;margin:24px}}section{{background:#181b2a;border-radius:10px;padding:14px;margin:0 0 18px}}
h3{{margin:0 0 8px}}small{{color:#8a93b8}}span{{color:#111;font:700 11px system-ui;padding:3px 8px;border-radius:9px;margin-left:6px}}
img{{max-width:100%;border-radius:6px}}code{{color:#9fb2ff}}</style><h2>Recursos usados neste projeto</h2>
<p>Politica de aprovacao: <b>{self.aprovacao}</b>. Recursos pendentes so entram na producao em massa depois de aprovados (se a politica exigir).</p>{''.join(linhas)}"""
        Path(caminho_html).write_text(html, encoding="utf-8")
        return caminho_html
