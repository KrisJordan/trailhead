import { NavLink, Outlet, useLoaderData } from "react-router-dom";

const activeTabClass = 'tab tab-active bg-secondary font-bold text-white rounded-box';

export function ModuleContext() {
    const moduleName = useLoaderData();
    return <div>
        <div role="tablist" className="tabs tabs-lg mb-2">
            <NavLink to="./run" role="tab" className={({ isActive }) => isActive ? activeTabClass : 'tab'}>Run</NavLink>
            <NavLink to="./repl" role="tab" className={({ isActive }) => isActive ? activeTabClass : 'tab'} aria-label="Interact">Interact</NavLink>
            <NavLink to="./gui" role="tab" className={({ isActive }) => isActive ? activeTabClass : 'tab'}>GUI</NavLink>
        </div>
        <div role="tabpanel" className="bg-base-100 border-base-300 rounded-box p-6">
            <Outlet context={{ module: moduleName }} />
        </div>
    </div >;
}