import { useOutletContext } from "react-router-dom";

export function ModuleIndex() {
    let info = useOutletContext();
    return <p>Module Index</p>
}