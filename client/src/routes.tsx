import App from "./App";

import { createBrowserRouter } from "react-router-dom";
import { PyModule } from "./PyModule";
import { ModuleContext } from "./ModuleContext";
import { ModuleRunner } from "./ModuleRunner";
import { moduleLoader } from "./api/module";
import { ModuleREPL } from "./ModuleREPL";
import { ModuleIndex } from "./ModuleIndex";
import { Home } from "./home/Home";
import { HomeIndex } from "./home/HomeIndex";



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
                element: <ModuleContext />,
                loader: moduleLoader,
                children: [
                    {
                        index: true,
                        element: <ModuleIndex />
                    },
                    {
                        path: "run",
                        element: <ModuleRunner />,
                    },
                    {
                        path: "repl",
                        element: <ModuleREPL />
                    }
                ]
            }
        ]
    },
    {
        path: "/new",
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
                        element: <ModuleRunner />,
                    },
                    {
                        path: "repl",
                        element: <ModuleREPL />
                    }
                ]
            }
        ]
    }
]);

export default router;