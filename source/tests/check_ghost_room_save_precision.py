"""The ectoplasm levels of the ghost room survive a save exactly. Compiles nothing.

The check runs the production [GhostRoom] writer of Seat::exportSeatToStream statement by statement on a small model
of std::ostream (precision, setprecision, defaultfloat output of doubles as %.<precision>g, unsigned and bool as numbers)
and reads the text back the way Seat::importSeatFromStream does (whitespace tokens, correctly rounded doubles). It asserts
the outcome: every tested fractional level, chosen apparatus and revive switch comes back bit for bit after three
save/load cycles, whatever precision the save file stream had before, and that precision is given back afterwards for
the records that follow. The old writer (stream precision only) is run too and must lose a level, so the check tells
the delivered behaviour from the lost one. Fixed values counted once on this branch: 10 fixed levels, 2000 seeded
random levels, inherited precisions 6, 3 and 17, 3 cycles.
"""
from pathlib import Path
import random
import re
import struct

repo = Path(__file__).resolve().parents[2]
seat = (repo / 'source/game/Seat.cpp').read_text(encoding='utf-8')


def body(text, signature):
    """Returns the brace-delimited body that follows the signature."""
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[opening + 1:end - 1]


def statements(text):
    """Splits code into top-level statements without comments."""
    text = re.sub(r'//[^\n]*', '', text)
    result, depth, current, quoted = [], 0, '', None
    for char in text:
        if quoted:
            quoted = None if char == quoted and current[-1:] != '\\' else quoted
        elif char in '"\'':
            quoted = char
        elif char in '(':
            depth += 1
        elif char in ')':
            depth -= 1
        if char == ';' and depth == 0 and not quoted:
            result.append(' '.join(current.split()))
            current = ''
        else:
            current += char
    return result


def operands(statement):
    """Splits an `os << a << b` statement into its operands."""
    parts, depth, current, quoted, index = [], 0, '', None, 0
    while index < len(statement):
        char = statement[index]
        if quoted:
            quoted = None if char == quoted else quoted
        elif char in '"\'':
            quoted = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if not quoted and depth == 0 and statement.startswith('<<', index):
            parts.append(current.strip())
            current = ''
            index += 2
            continue
        current += char
        index += 1
    parts.append(current.strip())
    assert parts[0] == 'os', statement
    return parts[1:]


class Stream:
    """The parts of std::ostream the writer uses: precision and default float formatting."""

    def __init__(self, precision):
        self.precision = precision
        self.text = ''


DIGITS = {'std::numeric_limits<double>::max_digits10': 17}


def write(block, stream, seat_values):
    """Runs the production writer statements (text or parsed list) on the stream model."""
    saved = {}
    for statement in statements(block) if isinstance(block, str) else block:
        match = re.fullmatch(r'const std::streamsize (\w+) = os\.precision\(\)', statement)
        if match:
            saved[match.group(1)] = stream.precision
            continue
        match = re.fullmatch(r'os\.precision\((\w+)\)', statement)
        if match:
            stream.precision = saved[match.group(1)]
            continue
        for operand in operands(statement):
            if operand.startswith('"'):
                stream.text += operand[1:-1].replace('\\n', '\n')
            elif operand.startswith("'"):
                stream.text += operand[1:-1]
            elif operand.startswith('std::setprecision('):
                stream.precision = DIGITS[operand[len('std::setprecision('):-1]]
            elif operand == 'std::defaultfloat':
                pass
            elif operand == 'mEctoplasmLevels':
                stream.text += '%.*g' % (stream.precision, seat_values['levels'])
            elif operand == 'static_cast<uint32_t>(mGhostProduct)':
                stream.text += str(seat_values['product'])
            elif operand == 'mGhostRevive':
                stream.text += '1' if seat_values['revive'] else '0'
            else:
                raise AssertionError(('operand of the writer not modelled', operand))


READER = body(seat, 'bool Seat::importSeatFromStream(')
assert 'is >> mEctoplasmLevels >> product >> mGhostRevive >> str' in READER[READER.index('if(str == "[GhostRoom]")'):]


def load(text):
    """Reads the record back like the production reader: whitespace tokens, exact double conversion."""
    tokens = text.split()
    assert tokens[0] == '[GhostRoom]' and tokens[4] == '[/GhostRoom]', tokens
    return {'levels': float(tokens[1]), 'product': int(tokens[2]), 'revive': tokens[3] == '1'}


exporter = body(seat, 'bool Seat::exportSeatToStream(')
start = exporter.index('os << "[GhostBells]')
start = exporter.index(';', exporter.index('os << " [/GhostBells]', start)) + 1
end = exporter.index('    os << "[Merchant]', start)
block = exporter[start:end]
assert '[GhostRoom]' in block
parsed = statements(block)


def bits(value):
    """Returns the exact bit pattern of a double."""
    return struct.pack('<d', value)


rng = random.Random(1078)
levels = [0.0, 0.1 + 0.2, 1.0 / 3.0, 2.0 / 3.0, 0.12345678901234566, 0.99999999999999989, 1.2345678901234567e-12,
          8.1234567890123444, 9.999999999999998, 123456.78901234567]
levels += [rng.uniform(0.0, 10.0) for _ in range(1000)] + [rng.uniform(0.0, 1.0) * 10 ** rng.randint(-8, 6) for _ in range(1000)]
for precision in (6, 3, 17):
    for index, level in enumerate(levels):
        record = {'levels': level, 'product': index % 3, 'revive': index % 2 == 0}
        for cycle in range(3):
            stream = Stream(precision)
            write(parsed, stream, record)
            assert stream.precision == precision, ('the writer gives back the inherited precision', precision)
            restored = load(stream.text)
            assert bits(restored['levels']) == bits(level), (precision, level, stream.text, 'exact ectoplasm levels')
            assert restored['product'] == record['product'] and restored['revive'] == record['revive']
            record = restored

# An old save written with 6 digits still loads (the reader is unchanged) and goes on exactly from the loaded value.
old = load('[GhostRoom] 1.125 1 0 [/GhostRoom]')
assert old == {'levels': 1.125, 'product': 1, 'revive': False}
# The writer as it was after the loss: the stream precision of the save file decides, and a level is lost.
lost = Stream(6)
write('os << "[GhostRoom] " << mEctoplasmLevels << \' \' << static_cast<uint32_t>(mGhostProduct)\n'
      '   << \' \' << mGhostRevive << " [/GhostRoom]\\n";', lost, {'levels': 1.0 / 3.0, 'product': 0, 'revive': True})
assert load(lost.text)['levels'] != 1.0 / 3.0, 'the lost behaviour is told apart'
print('ghost room save precision: %d levels x 3 precisions x 3 cycles exact, stream precision kept: ok' % len(levels))
