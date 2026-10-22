"""英美拼写变体分组，供判分函数独立复用。"""

SPELLING_VARIANT_GROUPS: tuple[frozenset[str], ...] = (
    frozenset(("color", "colour")),
    frozenset(("center", "centre")),
    frozenset(("organize", "organise")),
    frozenset(("traveler", "traveller")),
    frozenset(("analyze", "analyse")),
    frozenset(("defense", "defence")),
    frozenset(("license", "licence")),
    frozenset(("favorite", "favourite")),
    frozenset(("honor", "honour")),
    frozenset(("labor", "labour")),
    frozenset(("neighbor", "neighbour")),
    frozenset(("theater", "theatre")),
    frozenset(("meter", "metre")),
    frozenset(("traveled", "travelled")),
    frozenset(("canceled", "cancelled")),
    frozenset(("modeling", "modelling")),
    frozenset(("program", "programme")),
    frozenset(("catalog", "catalogue")),
    frozenset(("dialog", "dialogue")),
    frozenset(("gray", "grey")),
    frozenset(("toward", "towards")),
    frozenset(("fulfill", "fulfil")),
    frozenset(("jewelry", "jewellery")),
    frozenset(("enrollment", "enrolment")),
)

_VARIANT_GROUP_BY_WORD = {
    spelling: group_index
    for group_index, group in enumerate(SPELLING_VARIANT_GROUPS)
    for spelling in group
}


def get_variant_group(word: str) -> int | None:
    """返回单词所属的英美变体组编号，没有映射时返回 None。"""
    return _VARIANT_GROUP_BY_WORD.get(word)
