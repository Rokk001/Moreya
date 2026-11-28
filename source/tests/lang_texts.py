"""Reader of the English language texts of the content for the checks (localization plan R11).

A check that compared an English text in the source code compares the text of the language file now: it looks up
the language key it finds in the code with english_texts(). The texts lie in the content package lang-en
(texts/*.txt, lines "<key>=<text>"); without the content the function returns None.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import content_packages  # noqa: E402


def english_texts(repo):
    """The entries of every text file of the package lang-en as {key: text}, "\n" kept as written, or None."""
    folder = content_packages.packages(repo).get('lang-en')
    if folder is None:
        return None
    texts = {}
    for path in sorted((folder / 'texts').glob('*.txt')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                texts[key] = value
    return texts
