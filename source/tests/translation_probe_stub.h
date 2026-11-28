// Stand-in of the text reference functions of utils/Translation.h for the small probes of the check scripts, which
// compile single functions of the game sources without the language system. The functions have the signatures of
// utils/Translation.h (a probe that also compiles a game source gets its calls linked to them) and write the same wire
// format as Translation::makeReference ("@<key>|<name>=<value>", values in name order) for values without special
// characters; the real functions are tested by test_Translation.cpp. Include it in one file of a probe only.
#include <map>
#include <string>

namespace Translation
{
//! \brief The text reference of the key with its values.
std::string makeReference(const std::string& key, const std::map<std::string, std::string>& values)
{
    std::string reference = "@" + key;
    for(const std::pair<const std::string, std::string>& value : values)
        reference += "|" + value.first + "=" + value.second;
    return reference;
}

//! \brief The text reference of the key without values.
std::string makeReference(const std::string& key)
{
    return "@" + key;
}

//! \brief The text reference of a name with its fallback text in the value "_".
std::string makeNameReference(const std::string& key, const std::string& fallback)
{
    std::map<std::string, std::string> values;
    values["_"] = fallback;
    return makeReference(key, values);
}

//! \brief The id as a part of a key: lowercase letters.
std::string toKeyPart(const std::string& id)
{
    std::string result = id;
    for(std::string::size_type i = 0; i < result.size(); ++i)
    {
        if((result[i] >= 'A') && (result[i] <= 'Z'))
            result[i] = static_cast<char>(result[i] - 'A' + 'a');
    }
    return result;
}
}
