import unittest

import criar_video as cv

BASE = {"nome": "Canal Teste", "idioma": "portugues do Brasil", "segundos_por_imagem": 6,
        "proporcao_video": 0.5, "regras_globais": ["Sem palavrões"]}


class TestPromptNucleo(unittest.TestCase):
    def test_legado_sem_bloco(self):
        p = cv.montar_prompt_roteiro(dict(BASE), "E se a Lua sumisse?", 60, [], "curiosidades")
        self.assertNotIn("NÚCLEO EDITORIAL", p)

    def test_nucleo_ativo(self):
        c = dict(BASE, nucleo_editorial={"ativo": True})
        p = cv.montar_prompt_roteiro(c, "E se a Lua sumisse?", 60, [], "curiosidades")
        self.assertIn("NÚCLEO EDITORIAL", p)
        self.assertIn("especulativo_what_if", p)
        self.assertIn("Sem palavrões", p)

    def test_perfil_manual(self):
        c = dict(BASE, nucleo_editorial={"ativo": True})
        p = cv.montar_prompt_roteiro(c, "tema", 60, [], "curiosidades", perfil="humor_leve")
        self.assertIn("humor_leve", p)

    def test_perfil_invalido_encerra(self):
        c = dict(BASE, nucleo_editorial={"ativo": True})
        with self.assertRaises(SystemExit):
            cv.montar_prompt_roteiro(c, "tema", 60, [], "curiosidades", perfil="nao_existe")


if __name__ == "__main__":
    unittest.main()
