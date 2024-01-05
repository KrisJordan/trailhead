import { Icon } from "@iconify/react/dist/iconify.js";
import { useEffect } from "react";
import { useDispatch } from "react-redux";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";

export interface HomeContext {
    navigateToModule: (module: string) => void;
}

export function Home() {
    const params = useParams();
    console.log("params", params);
    const module = params.moduleName || null;
    const dispatch = useDispatch();

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
    if (module) {
        moduleJsx = <li>{module}</li>;
    }

    return <>
        <div className="navbar bg-neutral text-neutral-content rounded-box mb-2">
            <div className="breadcrumbs flex-1 ">
                <ul className="text-xl text-white font-black">
                    <li><NavLink to="/new" aria-disabled="true"><Icon icon="mdi:forest-outline" className="mx-2" /> Trailhead</NavLink></li>
                    {moduleJsx}
                </ul>
                <div className="divider lg:divider-horizontal divider-secondary" />
                <div className="m-0 p-0 invisible lg:visible">The Adventure Starts Here</div>
            </div>
            <div className="flex-none"><div className="tooltip tooltip-bottom tooltip-primary mr-4" data-tip="Connected"><div className="badge badge-lg badge-primary mt-2"></div></div></div>
        </div>
        <Outlet context={{ navigateToModule }}></Outlet>
    </>;
}