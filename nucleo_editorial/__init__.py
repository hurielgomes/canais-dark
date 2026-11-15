"""Nucleo editorial: perfis narrativos, resolucao e blocos de prompt."""
from .viral_story_engine import construir_plano, bloco_prompt, avaliar_roteiro, otimizar_roteiro
from .resolver import (
    PerfilInvalido, canal_usa_nucleo, listar_perfis, obter_perfil,
    recomendar_perfis, resolver_perfil,
)
from .blocos_prompt import montar_bloco_editorial

__all__ = [
    "PerfilInvalido", "canal_usa_nucleo", "listar_perfis", "obter_perfil",
    "recomendar_perfis", "resolver_perfil", "montar_bloco_editorial",
]
