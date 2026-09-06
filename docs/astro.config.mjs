import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightLlmsTxt from "starlight-llms-txt";

export default defineConfig({
  site: "https://cmendezs.github.io",
  base: "/mcp-facture-electronique-fr/",
  integrations: [
    starlight({
      title: "mcp-facture-electronique-fr",
      description: "MCP server exposing the AFNOR XP Z12-013 APIs for French electronic invoicing (Compatible Solution)",
      customCss: ["./src/styles/docs-theme.css"],
      social: [
        { icon: "github", label: "GitHub", href: "https://github.com/cmendezs/mcp-facture-electronique-fr" },
      ],
      locales: {
        root: { label: "English", lang: "en" },
        fr: { label: "Français", lang: "fr" },
      },
      sidebar: [
        { label: "Overview", link: "/" },
        { label: "Tools", link: "/tools/" },
        { label: "Changelog", link: "/changelog/" },
        { label: "Contributing", link: "/contributing/" },
        { label: "Security", link: "/security/" },
        { label: "Code of Conduct", link: "/code-of-conduct/" },
      ],
      plugins: [
        starlightLlmsTxt({
          projectName: "mcp-facture-electronique-fr",
          description: "MCP server exposing the AFNOR XP Z12-013 APIs for French electronic invoicing (Compatible Solution)",
          customSets: [
            {
              label: "Key links",
              description: "PyPI and MCP registry entries",
              links: ["https://pypi.org/project/mcp-facture-electronique-fr/", "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.cmendezs/mcp-facture-electronique-fr"],
            },
          ],
        }),
      ],
    }),
  ],
});
