import { useNavigate, useOutletContext } from "react-router-dom";

export function ModuleRunner() {
    const { module } = useOutletContext() as { module: string };
    const navigate = useNavigate();
    return <p>Module Runner: {module} - <a onClick={() => navigate(".", { replace: true })}>Reload</a></p>
}