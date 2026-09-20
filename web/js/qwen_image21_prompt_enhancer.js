import { app } from "../../scripts/app.js";
import { addCompletionRecoveryButton } from "./completion_recovery_ui.mjs";


const NODE_ID = "QwenImage21PromptEnhancerT8";


app.registerExtension({
    name: "T8.QwenImage21PromptEnhancer",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;
        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            originalOnNodeCreated?.apply(this, arguments);
            addCompletionRecoveryButton(this, NODE_ID);
        };
    },
});
