"""Convert our escaped, read-only view into a DOM description, never executable HTML."""
from html.parser import HTMLParser

TAGS = frozenset('section article div span p b strong em small h2 h3 h4 a svg g path rect circle ellipse line polyline text i'.split())
ATTRS = frozenset('class id role aria-label data-live-key viewbox x y x1 x2 y1 y2 cx cy r rx ry width height d points fill stroke stroke-width stroke-opacity fill-opacity stroke-linecap stroke-linejoin stroke-dasharray text-anchor font-size opacity transform href target'.split())


class ViewTree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {'tag': 'div', 'attrs': {}, 'children': []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        if tag not in TAGS:
            raise ValueError('Unsupported live-view element')
        node = {'tag': tag, 'attrs': {name: value for name, value in attrs if name in ATTRS and value is not None}, 'children': []}
        self.stack[-1]['children'].append(node)
        self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if len(self.stack) < 2 or self.stack[-1]['tag'] != tag:
            raise ValueError('Unbalanced live-view markup')
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1]['children'].append(data)


def view_tree(markup):
    parser = ViewTree()
    parser.feed(markup)
    parser.close()
    if len(parser.stack) != 1:
        raise ValueError('Unclosed live-view markup')
    return parser.root['children']
