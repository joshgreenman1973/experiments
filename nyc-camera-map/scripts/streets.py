"""Street-name normalization shared by the intersection index and the ticket parser.

The two sources spell the same street very differently. NYC Centerline says
"AVE N" and "88 ST"; a Department of Finance camera ticket says "AVENUE N" and
"88TH ST". Everything here exists to make those two strings collide.
"""
import re

# Suffixes and common words, collapsed to one canonical token each.
SUFFIX = {
    'AVENUE': 'AVE', 'AV': 'AVE', 'AVE': 'AVE',
    'STREET': 'ST', 'STR': 'ST', 'ST': 'ST',
    'ROAD': 'RD', 'RD': 'RD',
    'BOULEVARD': 'BLVD', 'BLVD': 'BLVD', 'BLV': 'BLVD',
    'PLACE': 'PL', 'PL': 'PL',
    'DRIVE': 'DR', 'DR': 'DR',
    'PARKWAY': 'PKWY', 'PKWY': 'PKWY', 'PKY': 'PKWY', 'PARKWY': 'PKWY',
    'EXPRESSWAY': 'EXPY', 'EXPWY': 'EXPY', 'EXPY': 'EXPY',
    'HIGHWAY': 'HWY', 'HWY': 'HWY',
    'TURNPIKE': 'TPKE', 'TPKE': 'TPKE', 'TPK': 'TPKE',
    'LANE': 'LN', 'LN': 'LN',
    'COURT': 'CT', 'CT': 'CT',
    'TERRACE': 'TER', 'TER': 'TER', 'TERR': 'TER',
    'CIRCLE': 'CIR', 'CIR': 'CIR',
    'SQUARE': 'SQ', 'SQ': 'SQ',
    'BRIDGE': 'BRG', 'BRG': 'BRG',
    'PLAZA': 'PLZ', 'PLZ': 'PLZ',
    'CONCOURSE': 'CONC', 'CONC': 'CONC',
    'BROADWAY': 'BROADWAY', 'BWAY': 'BROADWAY',
    'CRESCENT': 'CRES', 'CRES': 'CRES',
    'WALK': 'WALK', 'LOOP': 'LOOP', 'PATH': 'PATH', 'WAY': 'WAY',
    'ALLEY': 'ALY', 'ALY': 'ALY',
    'ENTRANCE': 'ENT', 'EXIT': 'EXIT', 'RAMP': 'RAMP',
    'EXTENSION': 'EXT', 'EXT': 'EXT',
    'HEIGHTS': 'HTS', 'HTS': 'HTS',
    'ISLAND': 'IS', 'IS': 'IS',
    'JUNCTION': 'JCT', 'JCT': 'JCT',
    'MOUNT': 'MT', 'MT': 'MT',
    'POINT': 'PT', 'PT': 'PT',
    'SAINT': 'ST.', 'ROW': 'ROW', 'OVAL': 'OVAL', 'SLIP': 'SLIP',
    'ESPLANADE': 'ESPL', 'ESPL': 'ESPL',
    'BOARDWALK': 'BRDWLK', 'BRDWLK': 'BRDWLK',
    'SERVICE': 'SVC', 'SVC': 'SVC', 'SVRD': 'SVC RD',
    'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W',
    'NO': 'N', 'SO': 'S', 'EA': 'E', 'WE': 'W',
    'TPK': 'TPKE', 'TRPK': 'TPKE', 'TURNPK': 'TPKE',
    'FREEWAY': 'FWY', 'FWY': 'FWY',
    'EXPWYEXT': 'EXPY EXT', 'EXPRESSWY': 'EXPY',
    'SVCRD': 'SVC RD', 'SERVICE RD': 'SVC RD', 'SR': 'SVC RD',
}

# Streets the ticket data and the Centerline file simply call different things.
ALIAS = {
    'FDR DR': 'FRANKLIN D ROOSEVELT DR',
    'F D R DR': 'FRANKLIN D ROOSEVELT DR',
    'LIE': 'LONG ISLAND EXPY',
    'L I E': 'LONG ISLAND EXPY',
    'BQE': 'BROOKLYN QUEENS EXPY',
    'B Q E': 'BROOKLYN QUEENS EXPY',
    'WEST SIDE HWY': 'JOE DIMAGGIO HWY',
    'HARLEM RIVER DR': 'HARLEM RIVER DR',
    'ROCKAWAY FWY': 'ROCKAWAY FWY',
    'GRAND CENTRAL PKWY': 'GRAND CENTRAL PKWY',
}

# Spelled-out ordinals: tickets say THIRD AVE, Centerline says 3 AVE.
WORD_ORDINAL = {
    'FIRST': '1', 'SECOND': '2', 'THIRD': '3', 'FOURTH': '4', 'FIFTH': '5',
    'SIXTH': '6', 'SEVENTH': '7', 'EIGHTH': '8', 'NINTH': '9', 'TENTH': '10',
    'ELEVENTH': '11', 'TWELFTH': '12',
}

# Suffixes that get glued onto the preceding word when a clerk drops a space.
GLUED = ('STREET', 'AVENUE', 'PARKWAY', 'BOULEVARD', 'EXPWY', 'TPKE', 'PKWY',
         'BLVD', 'AVE', 'ST', 'RD', 'PL', 'DR', 'LN', 'CT', 'TER')
_GLUE_RE = re.compile(r'(?<=[A-Z0-9])(' + '|'.join(GLUED) + r')$')
_ORD_GLUE = re.compile(r'\b(\d+)(ST|ND|RD|TH)(?=[A-Z])')
_DIRNUM = re.compile(r'\b([NSEW])(\d)')
_LETTERNUM = re.compile(r'(?<=[A-Z])(\d+(?:ST|ND|RD|TH)\b)')


def deglue(s):
    """Put back spaces the ticket system dropped: E149TH ST, 235THST, MAINST."""
    s = _ORD_GLUE.sub(r'\1\2 ', s)          # 235THST -> 235TH ST
    s = _DIRNUM.sub(r'\1 \2', s)            # E149TH -> E 149TH
    words = []
    for w in s.split(' '):
        if len(w) > 4 and not w.isdigit():
            m = _GLUE_RE.search(w)
            # only split when what is left is a plausible street name
            if m and len(w) - len(m.group(1)) >= 3:
                w = w[:m.start()] + ' ' + m.group(1)
        words.append(w)
    return ' '.join(words)

# Travel direction as recorded on a ticket, not part of the street name.
DIR_PREFIX = re.compile(r'^(NB|SB|EB|WB|N/B|S/B|E/B|W/B)\b\s*')
DIR_PAREN = re.compile(r'\((?:N|S|E|W)/B\)')
ORDINAL = re.compile(r'\b(\d+)(ST|ND|RD|TH)\b')


def normalize(name):
    """Canonical form of a street name for cross-source matching."""
    if not name:
        return ''
    s = name.upper().strip()
    s = DIR_PAREN.sub(' ', s)
    s = s.replace('&', ' AND ')
    s = re.sub(r"[.,'`]", '', s)
    s = re.sub(r'[-/]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = deglue(s)
    s = ORDINAL.sub(r'\1', s)            # 88TH -> 88
    s = re.sub(r'\s+', ' ', s).strip()
    parts = [WORD_ORDINAL.get(p, p) for p in s.split(' ')]
    parts = [SUFFIX.get(p, p) for p in parts]
    # "AVENUE N" and "AVE N" both land on "AVE N"; drop noise words.
    parts = [p for p in parts if p not in ('THE', 'OF')]
    s = ' '.join(parts).strip()
    return ALIAS.get(s, s)


def strip_direction(s):
    """Split a ticket street string into (travel direction, street name)."""
    s = s.upper().strip()
    direction = ''
    m = DIR_PREFIX.match(s)
    if m:
        direction = m.group(1).replace('/', '')
        s = s[m.end():]
    m = DIR_PAREN.search(s)
    if m:
        direction = m.group(0).strip('()').replace('/', '')
        s = DIR_PAREN.sub(' ', s)
    return direction, re.sub(r'\s+', ' ', s).strip()


def variants(norm):
    """Alternate spellings worth trying when the canonical form misses.

    Returned as an ordered list with the canonical name first: several variants
    can match different corners, so the caller's iteration order decides the
    answer, and a set would make that order vary between runs.
    """
    out = {norm}
    # Centerline files some streets with and without a leading direction letter.
    m = re.match(r'^([NSEW]) (.+)$', norm)
    if m:
        out.add(m.group(2))
    m = re.match(r'^(.+) ([NSEW])$', norm)
    if m:
        out.add(m.group(1))
    for d in ('E', 'W', 'N', 'S'):
        out.add(d + ' ' + norm)
    # The Rockaways: tickets write "B 47 ST" for "BEACH 47 ST".
    if norm.startswith('B '):
        out.add('BEACH ' + norm[2:])
    out.add(norm.replace(' SVC RD', '').replace(' SERVICE RD', ''))
    out.add(re.sub(r'\bEXIT \d+\b', '', norm).strip())
    out.add(re.sub(r'\b(OFFRAMP|ONRAMP|RAMP|ENT|EXIT|EXT)\b', '', norm).strip())
    rest = sorted(v for v in out if v and v != norm)
    return ([norm] if norm else []) + rest
