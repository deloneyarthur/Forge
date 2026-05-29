"""forge.core — blessed primitives (clock, seed, logging, contracts check).

Hard rule #8: only forge.core.clock may import datetime.now / utcnow; only
forge.core.seed may instantiate RNGs. All callers route through these.
"""
