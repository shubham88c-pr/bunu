from . import structure, missing, duplicates, types, strings, numeric, datetime

# Order = order of appearance in the engine. Each module exposes
# ``dataset(ctx)`` and/or ``column(ctx, i)`` returning a list of Issue.
ALL = [structure, missing, duplicates, types, strings, numeric, datetime]
