def assert_ranges(units: list[dict]):
    """
    Garante que end_line >= start_line em todas as unidades.
    Lança ValueError se houver violação.
    """
    for u in units:
        r = u.get("range") or {}
        sl = r.get("start_line")
        el = r.get("end_line")
        # Só valida se ambos existirem e forem int
        if isinstance(sl, int) and isinstance(el, int):
            if el < sl:
                kind = u.get("kind", "unknown")
                name = u.get("name", u.get("id", "unnamed"))
                raise ValueError(f"Invalid range for unit '{name}' ({kind}): end_line({el}) < start_line({sl})")
