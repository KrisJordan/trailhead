import { Icon } from "@iconify/react/dist/iconify.js";
import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { SocketState } from "../features/socket";
import { RootState } from "../app/store";
import { ModuleState } from "../features/module";

export interface HomeContext {
    navigateToModule: (module: string) => void;
}

export function Home() {
    const module = useSelector<RootState, ModuleState>((state) => state.module);
    const dispatch = useDispatch();
    const { readyState } = useSelector<RootState, SocketState>((state) => state.socket);

    // const [module, setModule] = useState<string | null>(null);
    const navigate = useNavigate();

    useEffect(() => {
        dispatch({ type: 'socket/connect' });

        return () => {
            dispatch({ type: 'socket/disconnect' });
        }
    }, []);

    const navigateToModule = (moduleStr: string) => {
        // setModule(moduleStr);
        navigate(`/module/${moduleStr}`);
    };

    let moduleJsx = null;
    if (module.selected) {
        moduleJsx = <li>{module.selected}</li>;
    }

    let navline = null;
    if (module.info) {
        if (module.info.doc !== "") {
            navline = <>
                <div className="md:divider md:divider-horizontal md:divider-secondary" />
                <div className="m-0 p-0 hidden md:block overflow-hidden text-nowrap text-ellipsis">{module.info.doc}</div>
            </>
        }
    } else {
        navline = <>
            <div className="md:divider md:divider-horizontal md:divider-secondary" />
            <div className="m-0 p-0 invisible md:visible">The Adventure Starts Here</div>
        </>
    }

    let indicator = null;
    switch (readyState) {
        case WebSocket.CONNECTING:
            indicator = <div className="tooltip tooltip-bottom tooltip-primary mr-4" data-tip="Connecting">
                <div className="badge badge-lg badge-accent mt-2"></div>
            </div>;
            break;
        case WebSocket.OPEN:
            indicator = <div className="tooltip tooltip-bottom tooltip-primary mr-4" data-tip="Connected">
                <div className="badge badge-lg badge-primary mt-2"></div>
            </div>;
            break;
        case WebSocket.CLOSING:
        case WebSocket.CLOSED:
            indicator = <div className="tooltip tooltip-bottom tooltip-error text-white mr-4" data-tip="Please Restart Trailhead and Refresh">
                <div className="badge badge-lg badge-error mt-2 font-bold">Disconnected</div>
            </div>;
            break;
    }

    return <>
        <div className="navbar bg-neutral text-neutral-content rounded-box mb-2">
            <div className="breadcrumbs flex-1 ">
                <ul className="text-xl text-white font-black">
                    <li><NavLink to="/" replace={true} aria-disabled="true"><Icon icon="mdi:forest-outline" className="mx-2" /> Trailhead</NavLink></li>
                    {moduleJsx}
                </ul>
                {navline}
            </div>
            <div className="flex-none">{indicator}</div>
        </div>
        <Outlet context={{ navigateToModule }}></Outlet>
    </>;
}