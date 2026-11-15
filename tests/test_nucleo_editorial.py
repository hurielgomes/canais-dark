import json
import unittest
from pathlib import Path

from nucleo_editorial import (
    PerfilInvalido, canal_usa_nucleo, listar_perfis, montar_bloco_editorial,
    recomendar_perfis, resolver_perfil,
)
from nucleo_editorial.resolver import _dados

ROOT = Path(__file__).resolve().parents[1]
CAMPOS = {"nome", "descricao", "tom", "estrutura", "abertura", "aprofundamento", "velocidade",
          "exemplos_analogias", "tensao_curiosidade", "encerramento", "cta", "cuidados"}


def canal(**cfg):
    base = {"nome": "Canal Teste", "nicho": "ciência", "publico": "jovens", "tom": "leve",
            "regras": ["Sem palavrões"]}
    if cfg is not None:
        base["nucleo_editorial"] = {"ativo": True, "perfil_padrao": None,
                                    "perfis_permitidos": [], "perfis_bloqueados": [], **cfg}
    return base


def ids_categorias():
    dados = json.loads((ROOT / "motores" / "categorias.json").read_text(encoding="utf-8"))
    if isinstance(dados, dict):
        dados = dados.get("categories") or dados.get("categorias") or dados
    if isinstance(dados, dict):
        return list(dados)
    return [c["id"] if isinstance(c, dict) else c for c in dados]


class TestPerfis(unittest.TestCase):
    def test_oito_perfis_completos(self):
        perfis = listar_perfis()
        self.assertEqual(len(perfis), 8)
        for pid, p in perfis.items():
            self.assertTrue(CAMPOS <= set(p), f"{pid} sem campos: {CAMPOS - set(p)}")

    def test_mapa_aponta_perfis_existentes(self):
        perfis = set(listar_perfis())
        for cat, m in _dados()["categorias"].items():
            self.assertIn(m["padrao"], perfis, cat)
            self.assertTrue(set(m["compativeis"]) <= perfis, cat)

    def test_categorias_do_projeto_mapeadas(self):
        mapeadas = set(_dados()["categorias"])
        faltando = [c for c in ids_categorias() if c not in mapeadas]
        self.assertEqual(faltando, [], f"categorias sem mapa (caem em _padrao): {faltando}")


class TestResolver(unittest.TestCase):
    def test_canal_legado(self):
        c = {"nome": "exemplo"}
        self.assertFalse(canal_usa_nucleo(c))
        r = resolver_perfil(c, "curiosidades", "tema")
        self.assertEqual((r["modo"], r["perfil"]), ("legado", None))
        self.assertEqual(montar_bloco_editorial(c, "curiosidades", r), "")

    def test_manual_vence(self):
        r = resolver_perfil(canal(perfil_padrao="humor_leve"), "noticias", "e se", "narrativo_historia")
        self.assertEqual((r["perfil"], r["origem"]), ("narrativo_historia", "manual"))

    def test_perfil_padrao_do_canal(self):
        r = resolver_perfil(canal(perfil_padrao="humor_leve"), "noticias", "qualquer")
        self.assertEqual((r["perfil"], r["origem"]), ("humor_leve", "canal"))

    def test_bloqueio_vence_manual(self):
        r = resolver_perfil(canal(perfis_bloqueados=["humor_leve"]), "humor", "x", "humor_leve")
        self.assertNotEqual(r["perfil"], "humor_leve")
        self.assertIn("não permitido", r["justificativa"])

    def test_permitidos_restringem(self):
        recs = recomendar_perfis(canal(perfis_permitidos=["noticioso_objetivo"]), "curiosidades", "e se", 8)
        self.assertTrue(all(x["perfil"] == "noticioso_objetivo" for x in recs))

    def test_recomendacao_por_tema(self):
        r = resolver_perfil(canal(), "curiosidades", "E se a Lua sumisse?")
        self.assertEqual((r["perfil"], r["origem"]), ("especulativo_what_if", "recomendacao"))
        self.assertTrue(r["justificativa"])

    def test_perfil_invalido(self):
        with self.assertRaises(PerfilInvalido):
            resolver_perfil(canal(), "curiosidades", "x", "nao_existe")


class TestBloco(unittest.TestCase):
    def test_precedencia_e_identidade(self):
        c = canal()
        r = resolver_perfil(c, "curiosidades", "E se a Lua sumisse?")
        txt = montar_bloco_editorial(c, "curiosidades", r, "9x16", "classic", "E se a Lua sumisse?")
        ordem = [txt.index(s) for s in ("[1] REGRAS", "[2] IDENTIDADE", "[3] PERFIL",
                                        "[4] CATEGORIA", "[5] TEMA", "[6] FORMATO", "[7] MOTOR")]
        self.assertEqual(ordem, sorted(ordem))
        self.assertIn("Sem palavrões", txt)
        self.assertIn("tom: leve", txt)
        self.assertNotIn("prioridade máxima", txt.lower())


if __name__ == "__main__":
    unittest.main()
