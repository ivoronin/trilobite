# pylint: disable=C0116,C0115,C0114,C0103,R0903
from lark import Lark, Token

_GRAMMAR = """
?start: command

?command: "for" (_WS _ARTICLE)? _WS for_time -> for
        | "to" (_WS _ARTICLE)? _WS to_time   -> to

?for_time: FOR_TIME_HUMAN -> human
        | INT TIME_UNIT?  -> int

?to_time: TO_TIME_HUMAN -> human
        | INT           -> int

FOR_TIME_HUMAN: "few" _WS "hours"|"few" _WS "days"
TO_TIME_HUMAN: "tomorrow"
                |"next" _WS ("week"|"month")
                |"monday"|"mon"
                |"tuesday"|"tue"
                |"wednesday"|"wed"
                |"thursday"|"thu"
                |"friday"|"fri"
                |"weekend"|"saturday"|"sat"
                |"sunday"|"sun"
TIME_UNIT: "h"|"d"
_ARTICLE: "a"|"the"
_WS: WS

%import common.INT
%import common.WS
"""

def parse(command):
    parser = Lark(
        _GRAMMAR,
        parser='lalr',
        lexer_callbacks={
            'INT': lambda t: Token.new_borrow_pos(t.type, int(t), t)
        }
    )
    return parser.parse(command)
