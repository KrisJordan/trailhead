import { useSelector } from "react-redux";
import { NavLink, Outlet, useLoaderData } from "react-router-dom";
import { RootState } from "./app/store";
import { ModuleInfo } from "./features/module";

const activeTabClass = 'tab tab-active bg-secondary font-bold text-white rounded-box';

export function ModuleContext() {
    const moduleInfo = useSelector<RootState, ModuleInfo | null>((state) => state.module.info);
    const moduleName = useLoaderData();
    return <div>
        <div role="tablist" className="tabs tabs-lg mb-2">
            <NavLink to="./run" role="tab" className={({ isActive }) => isActive ? activeTabClass : 'tab'}>Run</NavLink>
            <NavLink to="./repl" role="tab" className={({ isActive }) => isActive ? activeTabClass : 'tab'} aria-label="Interact">Interact</NavLink>
            {moduleInfo?.global_vars?.["__template__"] && (
                <NavLink to="./gui" role="tab" className={({ isActive }) => isActive ? activeTabClass : 'tab'}>GUI</NavLink>
            )}
        </div>
        <div role="tabpanel" className="bg-base-100 border-base-300 rounded-box p-6">
            <Outlet context={{ module: moduleName }} />
        </div>
    </div >;
}