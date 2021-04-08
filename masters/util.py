from typing import Union


def str_to_int(val: str, none_is_zero: bool = True) -> Union[int, None]:
    # convenience function to strip down to raw integer
    digits = ''.join(c for c in val if c.isdigit())
    if digits:
        return int(digits)
    else:
        if none_is_zero:
            return 0
        else:
            return None


def round_title_to_int(round: str) -> int:
    return int(round.replace('r', ''))


def to_score(score):
    if score and score != '--' and score != 'E':
        return int(score)
    else:
        return 0


class JinjaFormatter:
    """ Helper functions for Jinja templating since I couldn't find an easy way to
        make an entire module accessible."""

    @staticmethod
    def score(score: int) -> str:
        try:
            int(score)
        except:
            return score
        if score > 0:
            return f'+{score}'
        elif score == 0:
            return 'E'
        else:
            return f'{score}'
