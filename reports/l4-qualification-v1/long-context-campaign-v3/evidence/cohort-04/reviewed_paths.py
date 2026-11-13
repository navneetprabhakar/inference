def normalize(path):
    absolute = path.startswith('/')
    parts = []

    for part in path.split('/'):
        if not part or part == '.':
            continue
        if part == '..':
            if parts and parts[-1] != '..':
                parts.pop()
            elif not absolute:
                parts.append('..')
        else:
            parts.append(part)

    result = '/'.join(parts)
    if absolute:
        return '/' + result
    return result or '.'


def test_normalize():
    cases = {
        '/a//b/./c': '/a/b/c',
        '/a/../../b': '/b',
        'a/../../b': '../b',
        '': '.',
        '../../a/../b': '../../b',
        'a/../../../b': '../../b',
        '/../../b': '/b',
        'a/..': '.',
        '///': '/',
        './': '.',
        'a/b/': 'a/b',
        '../..': '../..',
        '../a/..': '..',
        '.../.hidden/a..b': '.../.hidden/a..b',
        '.../..': '.',
    }
    for path, expected in cases.items():
        actual = normalize(path)
        assert actual == expected, (path, actual, expected)
        assert normalize(actual) == actual, (path, actual)


if __name__ == '__main__':
    test_normalize()
    print('All regression tests passed.')
