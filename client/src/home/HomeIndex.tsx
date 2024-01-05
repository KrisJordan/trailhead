import { NavLink, useNavigate } from "react-router-dom";

export function HomeIndex() {
    let navigate = useNavigate()
    return <>
        <div className="text-xl my-8">Welcome to Trailhead! Select a module or package below.</div>
        <ul className="menu menu-lg bg-base-100 rounded-box ">
            <li><NavLink to="./module/foo" className="w-full grid grid-cols-4 hover:bg-neutral-100"><span className="col-span-1">Foo</span> <span className="text-neutral-400 font-light italic col-span-3">Some sample functions</span></NavLink></li>
            <li><NavLink to="./module/bar" className="grid grid-cols-4 hover:bg-neutral-100"><span className="col-span-1">Bar</span> <span className="text-neutral-400 font-light italic col-span-3">Some more text</span></NavLink></li>
        </ul>
    </>;
}