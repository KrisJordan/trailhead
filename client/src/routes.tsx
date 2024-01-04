import App from "./App";

import { createBrowserRouter } from "react-router-dom";
import { PyModule } from "./PyModule";
import { ModuleContext } from "./ModuleContext";

function moduleLoader({ params }: any) {
    return params.moduleName;
}

const router = createBrowserRouter([
    {
        path: "/",
        element: <App />,
        children: [
            {
                path: "module/:moduleName/run",
                element: <PyModule />,
                loader: moduleLoader
            },
            {
                path: "view/:moduleName",
                element: <ModuleContext />
            }
        ]
    }
]);

export default router;