import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { emptyPluginConfigSchema } from "openclaw/plugin-sdk";
import { wechatDock, wechatPlugin } from "./src/channel.js";
import { setWeChatRuntime } from "./src/runtime.js";

const plugin = {
  id: "wechat",
  name: "WeChat",
  description: "WeChat channel plugin (Personal via Wechaty)",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    setWeChatRuntime(api.runtime);
    api.registerChannel({ plugin: wechatPlugin, dock: wechatDock });
  },
};

export default plugin;
