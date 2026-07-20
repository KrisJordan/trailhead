// Converts POSIX and Windows file paths to a dotted Python module path.
export function parseModuleFromFile(filePath: string) {
    return filePath
        .replace(/^\.[\\/]/, '')
        .replace(/[\\/]/g, '.')
        .replace(/\.py$/, '');
}
