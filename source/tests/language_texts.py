"""The English texts of the game for the checks: the texts that the code takes from the language files by key
(Translation::tr) are read from the package lang-en, so a check can still compare the text the player sees."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import campaign_packages  # noqa: E402


def english_texts():
    """{key: text} of every file in texts/ of the package lang-en; "\\n" in a text is a line break."""
    folder = campaign_packages.content_folder(REPO)
    texts = {}
    if folder is None:
        return texts
    for path in sorted((Path(folder) / 'lang-en' / 'texts').glob('*.txt')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                texts[key.strip()] = value.replace('\\n', '\n').replace('\\\\', '\\')
    return texts


def english(key):
    """The English text of a key; an empty text when the content or the key is missing."""
    return english_texts().get(key, '')


def _cpp_string(text):
    """The text as the body of a C++ string literal (octal escapes for everything but plain ASCII)."""
    result = []
    for byte in text.encode('utf-8'):
        if 32 <= byte < 127 and chr(byte) not in '"\\?':
            result.append(chr(byte))
        else:
            result.append('\\%03o' % byte)
    return ''.join(result)


def translation_stub():
    """C++ source of a stand-in for Translation::tr that answers with the English texts of the language files, for
    the probes that compile production functions without the language system."""
    rows = ''.join('        {"%s", "%s"},\n' % (_cpp_string(key), _cpp_string(text))
                   for key, text in sorted(english_texts().items()))
    return '''#include <map>
#include <string>
namespace Translation
{
inline const std::map<std::string, std::string>& probeTexts()
{
    static const std::map<std::string, std::string> texts = {
%s    };
    return texts;
}
inline std::string tr(const std::string& key)
{
    std::map<std::string, std::string>::const_iterator it = probeTexts().find(key);
    return (it == probeTexts().end()) ? key : it->second;
}
inline std::string tr(const std::string& key, const std::map<std::string, std::string>& values)
{
    std::string text = tr(key);
    for(std::map<std::string, std::string>::const_iterator it = values.begin(); it != values.end(); ++it)
    {
        const std::string placeholder = "{" + it->first + "}";
        for(std::string::size_type at = text.find(placeholder); at != std::string::npos; at = text.find(placeholder, at))
        {
            text.replace(at, placeholder.size(), it->second);
            at += it->second.size();
        }
    }
    return text;
}
}
''' % rows
