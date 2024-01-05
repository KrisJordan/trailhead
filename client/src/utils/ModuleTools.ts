// Converts '/' based file path to '.' based python module path
export function parseModuleFromFile(filePath: string) {
    return filePath.replace(/^\.\//, '').replace(/\//g, '.').replace('.py', '');
}