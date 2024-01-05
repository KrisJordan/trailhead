import { useEffect, PropsWithChildren } from 'react';
import { parseJsonMessage } from './Message';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from './app/store';
import { SocketState } from './features/socket';
import { FilesState } from './features/files';
import { ReadyState } from './utils/Socket';
import { NavLink } from 'react-router-dom';

export interface Tree {
    ns_type: 'tree'
    children: (Package | Module)[];
}

export interface Package {
    ns_type: 'package'
    name: string
    full_path: string
    children: (Package | Module)[];
}

export interface Module {
    ns_type: 'module'
    name: string
    full_path: string
}

function NamespaceTree() {
    const files = useSelector<RootState, FilesState>((state) => state.files);
    const readyState = useSelector<RootState, ReadyState>((state) => state.socket.readyState);
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
                        <NavLink to={"./module/" + item.full_path.substring(2).replace("\/", ".").replace(".py", "")} className="w-full grid grid-cols-4 hover:bg-neutral-100">
                            <span className="col-span-1">{item.name.replace(".py", "")}</span>
                            <span className="text-neutral-400 font-light italic col-span-3">TODO: docstring...</span>
                        </NavLink>
                    </li>);
                    break;
                case 'package':
                    children.push(<li key={item.full_path + item.name}><details><summary><a>{item.name}</a></summary>{buildTree(item)}</details></li>)
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