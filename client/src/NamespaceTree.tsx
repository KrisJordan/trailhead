import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from './app/store';
import { FilesState } from './features/files';
import { ReadyState } from './utils/Socket';
import { NavLink } from 'react-router-dom';

export interface Tree {
    ns_type: 'tree';
    children: (Package | Module)[];
}

export interface Package {
    ns_type: 'package';
    name: string;
    full_path: string;
    children: (Package | Module)[];
    docstring: string;
}

export interface Module {
    ns_type: 'module';
    name: string;
    full_path: string;
    docstring: string;
}

function NamespaceTree() {
    const files = useSelector<RootState, FilesState>((state) => state.files);
    const readyState = useSelector<RootState, ReadyState>((state) => state.socket.fileSocketReadyState);
    const dispatch = useDispatch();

    useEffect(() => {
        if (readyState === ReadyState.OPEN) {
            dispatch({
                type: 'socket/send',
                payload: { type: "LS", data: { path: "/" } }
            });
        }
    }, [readyState]);

    let buildTree = (tree: { children: (Module | Package)[] }) => {
        let children = [];
        for (let item of tree.children) {
            switch (item.ns_type) {
                case 'module':
                    children.push(<li key={item.full_path + item.name}>
                        <NavLink to={"./module/" + encodeURIComponent(item.full_path.substring(2).replace("\/", ".").replace(".py", ""))} className="w-full grid grid-cols-4 hover:bg-neutral-100">
                            <span className="col-span-1">{item.name.replace(".py", "")}</span>
                            <span className="text-neutral-400 font-light italic col-span-3 overflow-hidden text-ellipsis text-nowrap">{item.docstring}</span>
                        </NavLink>
                    </li>);
                    break;
                case 'package':
                    children.push(<li key={item.full_path + item.name}>
                        <details className="w-full">
                            <summary className="grid grid-cols-4">
                                <span className="col-span-1">{item.name}</span>
                                <span className="col-span-3 text-neutral-400 font-light italic overflow-hidden text-ellipsis text-nowrap">{item.docstring}</span>
                            </summary>
                            {buildTree(item)}
                        </details>
                    </li>)
                    break;
            }
        }
        return <ul>{children}</ul>
    };

    return <div className="menu menu-lg bg-base-100 rounded-box">
        {buildTree(files.collection)}
    </div>;
}

export default NamespaceTree;