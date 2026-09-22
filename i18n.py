"""Локализация: загрузка locales/*.json и функция t()."""
import json
import logging
import os

from config import LOCALES_DIR, SUPPORTED_LANGUAGES, DEFAULT_INTERFACE_LANGUAGE

logger = logging.getLogger(__name__)

_CACHE: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang in _CACHE:
        return _CACHE[lang]
    path = os.path.join(LOCALES_DIR, f"{lang}.json")
    if not os.path.isfile(path):
        path = os.path.join(LOCALES_DIR, f"{DEFAULT_INTERFACE_LANGUAGE}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.exception("Не удалось загрузить локализацию %s", lang)
        data = {}
    _CACHE[lang] = data
    return data


def t(lang: str, key: str, **kwargs) -> str:
    """t('ru', 'MENU.BATTLE') → '⚔️ BATTLE'. Ключи через точку."""
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_INTERFACE_LANGUAGE
    data = _load(lang)
    parts = key.split(".")
    node = data
    for p in parts:
        if isinstance(node, dict) and p in node:
            node = node[p]
        else:
            node = None
            break
    if node is None:
        return key
    if isinstance(node, str) and kwargs:
        try:
            return node.format(**kwargs)
        except KeyError:
            return node
    return node if isinstance(node, str) else key


def available_interface_languages() -> list[str]:
    return list(SUPPORTED_LANGUAGES)