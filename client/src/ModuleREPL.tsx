import { useOutletContext } from "react-router-dom";

export function ModuleREPL() {
    const { module } = useOutletContext() as { module: string };
    return <p>Module REPL: {module}</p>
}