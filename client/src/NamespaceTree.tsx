import { useState, useEffect, PropsWithChildren } from 'react';
import useWebSocket from './useWebSocket';
import { parseJsonMessage } from './Message';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from './app/store';
import { SocketState } from './features/socket';
import { FilesState } from './features/files';
import { ReadyState } from './utils/Socket';

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

interface NamespaceTreeProps {
    selectModule: (module: Module) => void;
}

function NamespaceTree(props: PropsWithChildren<NamespaceTreeProps>) {
    // const [files, setFiles] = useState<Tree>({ ns_type: 'tree', children: [] });
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
                    children.push(<li key={item.full_path + item.name} onClick={() => props.selectModule(item as Module)}><a>{item.name}</a></li>);
                    break;
                case 'package':
                    children.push(<li key={item.full_path + item.name}><details><summary><a>{item.name}</a></summary>{buildTree(item)}</details></li>)
                    break;
            }
        }
        return <ul>{children}</ul>
    };

    return <div className="menu menu-s rounded-lg max-w-xs flex-none w-25">
        {buildTree(files.collection)}
    </div>;
}

export default NamespaceTree;