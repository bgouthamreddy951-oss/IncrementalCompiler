
import re
from dataclasses import dataclass


@dataclass
class Token:
    type: str
    value: str
    line: int
    column: int


KEYWORDS = {
    "function", "import", "let", "int", "float",
    "string", "return", "if", "else", "while",
    "true", "false", "void"
}

TOKEN_PATTERN = re.compile(
    r"(?P<WHITESPACE>[ \t\r]+)"
    r"|(?P<NEWLINE>\n)"
    r"|(?P<COMMENT>//[^\n]*|#[^\n]*)"
    r"|(?P<FLOAT>\d+\.\d+)"
    r"|(?P<INTEGER>\d+)"
    r'|(?P<STRING>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
    r"|(?P<IDENTIFIER>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<OPERATOR>==|!=|<=|>=|&&|\|\||[+\-*/%=<>!])"
    r"|(?P<SYMBOL>[(){};,])"
)


def tokenize(source):
    tokens = []
    position = 0
    line = 1
    column = 1

    while position < len(source):
        match = TOKEN_PATTERN.match(source, position)

        if not match:
            char = source[position]
            raise SyntaxError(
                f"Illegal character {char!r} "
                f"at line {line}, column {column}"
            )

        kind = match.lastgroup
        value = match.group()
        token_line = line
        token_column = column

        if kind not in {"WHITESPACE", "NEWLINE", "COMMENT"}:
            if kind == "IDENTIFIER" and value in KEYWORDS:
                kind = "KEYWORD"

            tokens.append(
                Token(kind, value, token_line, token_column)
            )

        newline_count = value.count("\n")

        if newline_count:
            line += newline_count
            column = len(value) - value.rfind("\n")
        else:
            column += len(value)

        position = match.end()

    tokens.append(Token("EOF", "", line, column))
    return tokens


if __name__ == "__main__":
    sample = """
function add(a, b) {
    return a + b + 4;
}
"""

    for token in tokenize(sample):
        print(token)
