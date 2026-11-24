"""Read the data a BirdCast dashboard page embeds as window.__NUXT__.

The page ships its data as a JavaScript function call:
    window.__NUXT__=(function(a,b,...){return {...}}(lit1,lit2,...));
This parses that text as data, without running any JavaScript: a small
reader for JS literals (objects, arrays, strings, numbers, true/false/null,
void 0) in which bare names stand for the function's arguments.
"""
import json, re

class Reader:
    def __init__(self, s, env=None):
        self.s, self.i, self.env = s, 0, env or {}

    def ws(self):
        s, n = self.s, len(self.s)
        while self.i < n and s[self.i] in ' \t\r\n':
            self.i += 1

    def peek(self):
        self.ws()
        return self.s[self.i] if self.i < len(self.s) else ''

    def eat(self, ch):
        self.ws()
        if not self.s.startswith(ch, self.i):
            raise ValueError(f"expected {ch!r} at {self.i}: {self.s[self.i:self.i+60]!r}")
        self.i += len(ch)

    NUM = re.compile(r'-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
    IDENT = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*')

    def string(self):
        q = self.s[self.i]
        j = self.i + 1
        out = []
        while True:
            c = self.s[j]
            if c == '\\':
                nxt = self.s[j + 1]
                if nxt == 'u':
                    out.append(chr(int(self.s[j + 2:j + 6], 16))); j += 6; continue
                if nxt == 'x':
                    out.append(chr(int(self.s[j + 2:j + 4], 16))); j += 4; continue
                out.append({'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', '0': '\0'}.get(nxt, nxt)); j += 2; continue
            if c == q:
                self.i = j + 1
                return ''.join(out)
            out.append(c); j += 1

    def value(self):
        c = self.peek()
        if c == '{':
            return self.obj()
        if c == '[':
            return self.arr()
        if c in '"\'':
            return self.string()
        m = self.NUM.match(self.s, self.i)
        if m and (c.isdigit() or c in '-.'):
            self.i = m.end()
            t = m.group()
            return float(t) if any(x in t for x in '.eE') else int(t)
        m = self.IDENT.match(self.s, self.i)
        if not m:
            raise ValueError(f"unexpected {self.s[self.i:self.i+60]!r}")
        name = m.group(); self.i = m.end()
        if name == 'true': return True
        if name == 'false': return False
        if name == 'null': return None
        if name == 'void':
            self.value(); return None
        if name in ('Infinity', 'NaN'): return None
        if name == 'new':  # new Date(x) and the like -> x
            m2 = self.IDENT.match(self.s, self.i + (len(self.s[self.i:]) - len(self.s[self.i:].lstrip())))
            self.ws(); self.i = m2.end(); self.eat('(')
            a = None if self.peek() == ')' else self.value()
            while self.peek() == ',':
                self.eat(','); self.value()
            self.eat(')'); return a
        if name == 'Array':  # Array(n) -> n empty slots
            self.eat('('); n = self.value(); self.eat(')'); return [None] * int(n)
        if name not in self.env:
            raise ValueError(f"unknown name {name!r} at {self.i}")
        return self.env[name]

    def obj(self):
        self.eat('{'); out = {}
        while self.peek() != '}':
            c = self.peek()
            if c in '"\'':
                k = self.string()
            else:
                m = self.IDENT.match(self.s, self.i) or self.NUM.match(self.s, self.i)
                k = m.group(); self.i = m.end()
            self.eat(':'); out[k] = self.value()
            if self.peek() == ',': self.eat(',')
        self.eat('}'); return out

    def arr(self):
        self.eat('['); out = []
        while self.peek() != ']':
            out.append(self.value())
            if self.peek() == ',': self.eat(',')
        self.eat(']'); return out


def parse_nuxt(html):
    i = html.find('window.__NUXT__=')
    if i < 0:
        raise ValueError('no window.__NUXT__ in page')
    j = html.find('</script>', i)
    js = html[i + len('window.__NUXT__='):j].strip().rstrip(';')
    m = re.match(r'\(function\(([^)]*)\)\{', js)
    if not m:
        # plain object form
        return Reader(js).value()
    params = [p.strip() for p in m.group(1).split(',') if p.strip()]
    body_start = m.end()
    # find "return " then the object, then the closing "}(" args "))"
    r = js.index('return', body_start) + len('return')
    tail = js.rindex('}(')
    args_txt = js[tail + 2:]
    args_txt = args_txt[:args_txt.rindex(')')]  # drop final ')' of the outer paren
    args_txt = args_txt[:args_txt.rindex(')')]  # drop the call's ')'
    args = Reader('[' + args_txt + ']').value()
    env = dict(zip(params, args + [None] * (len(params) - len(args))))
    rd = Reader(js[r:tail], env)
    return rd.value()
