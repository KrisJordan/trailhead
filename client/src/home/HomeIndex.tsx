import NamespaceTree from "../NamespaceTree";

export function HomeIndex() {
    return <>
        <div className="text-xl my-8">Welcome to Trailhead! Select a module or package below.</div>
        <NamespaceTree></NamespaceTree>
    </>;
}