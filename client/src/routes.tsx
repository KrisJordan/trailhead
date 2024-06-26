import { createBrowserRouter } from "react-router-dom";
import { ModuleContext } from "./ModuleContext";
import { ModuleRunner } from "./ModuleRunner";
import { moduleLoader, runLoader, replLoader, guiLoader } from "./api/module";
import { ModuleREPL } from "./ModuleREPL";
import { ModuleIndex } from "./ModuleIndex";
import { Home } from "./home/Home";
import { HomeIndex } from "./home/HomeIndex";
import { GraphicalUI } from "./GraphicalUI";



const router = createBrowserRouter([
    {
        path: "/",
        element: <Home />,
        children: [
            {
                index: true,
                element: <HomeIndex />,
                loader: moduleLoader,
            },
            {
                path: "module/:moduleName",
                element: <ModuleContext />,
                loader: moduleLoader,
                children: [
                    {
                        index: true,
                        element: <ModuleIndex />
                    },
                    {
                        path: "run",
                        loader: runLoader,
                        element: <ModuleRunner />,
                    },
                    {
                        path: "repl",
                        loader: replLoader,
                        element: <ModuleREPL />
                    },
                    {
                        path: "gui",
                        loader: guiLoader,
                        element: <GraphicalUI />
                    }
                ]
            }
        ]
    }
]);

export default router;