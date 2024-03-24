import module, { ModuleInfo, clearModule, setModule } from "../features/module";
import store from "../app/store";
import router from "../routes";

export const runLoader = async ({ params }: any) => {
    store.dispatch({
        type: "runsocket/connect",
        payload: {
            module: params.moduleName,
            endpoint: `/ws/${params.moduleName}/run`
        }
    });
    return null;
};

export const replLoader = async ({ params }: any) => {
    store.dispatch({
        type: "runsocket/connect",
        payload: {
            module: params.moduleName,
            endpoint: `/ws/${params.moduleName}/repl`
        }
    });
    return null;
};

export const guiLoader = async ({ params }: any) => {
    store.dispatch({
        type: "runsocket/connect",
        payload: {
            module: params.moduleName,
            endpoint: `/ws/${params.moduleName}/repl_gui`
        }
    });
    return null;
}

export const moduleLoader = async ({ params, request }: any) => {
    if (params.moduleName) {
        // Load the module info
        let moduleInfoResponse = await fetch(`/api/module/${params.moduleName}`);
        if (moduleInfoResponse.status === 404) {
            // Redirect to home if the module doesn't exist
            router.navigate("/");
            return null;
        }

        let moduleInfo = await moduleInfoResponse.json() as ModuleInfo;
        store.dispatch(setModule({ module: params.moduleName, info: moduleInfo }));

        /* Here we "sniff" the module to see whether it looks like just function definitions and
           redirect to one of the top-level tools if so. */
        let target = `/module/${params.moduleName}`;

        /* This is a bit of a hack to make sure that we don't get into a redirect loop. */
        /* This also ensures that we don't jump to a different tab than the one a user is on. */
        /* The auto-redirect is only meant at the top-route level of the module, not at the individual
           tools which we are redirecting to. */
        const windowLocation = window.location.protocol + "//" + window.location.host;
        const requestUrl = decodeURIComponent(request.url.replace(windowLocation, ""));
        if (target === requestUrl) {
            if (moduleInfo.global_vars?.["__template__"]) {
                target += "/gui";
            } else if (moduleInfo.top_level_calls && moduleInfo.top_level_calls.length > 0) {
                target += "/run";
            } else if (moduleInfo.top_level_functions && moduleInfo.top_level_functions.length > 0) {
                target += "/repl";
            } else {
                target += "/run";
            }

            if (requestUrl !== target) {
                router.navigate(target);
            }
        }
    } else {
        store.dispatch(clearModule());
    }

    /* 
    Here we're using a router loader as a means for triggering an action that updates the
    redux store and then redirecting to the appropriate page. We're not actually loading data
    into the component being routed to directly, hence the null return.
    */
    return null;
}