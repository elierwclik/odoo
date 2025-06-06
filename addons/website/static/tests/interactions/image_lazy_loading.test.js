import { setupInteractionWhiteList, startInteractions } from "@web/../tests/public/helpers";

import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, Deferred } from "@odoo/hoot-dom";

import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { ImageLazyLoading } from "@website/interactions/image_lazy_loading";

setupInteractionWhiteList("website.image_lazy_loading");

describe.current.tags("interaction_dev");

test("images lazy loading removes height then restores it", async () => {
    const def = new Deferred();
    patchWithCleanup(ImageLazyLoading.prototype, {
        async willStart() {
            await Promise.all([
                new Promise((resolve) => setTimeout(resolve, 5000)),
                super.willStart(),
            ]);
            def.resolve();
        },
    });
    const { core } = await startInteractions(
        `
        <div>Fake surrounding
            <div id="wrapwrap">
                <img src="/web/image/website.library_image_08" loading="lazy" style="min-height: 100px;"/>
            </div>
        </div>
    `,
        { waitForStart: false }
    );
    expect(core.interactions).toHaveLength(1);
    expect("img").toHaveAttribute("src", "/web/image/website.library_image_08");
    expect("img").toHaveAttribute("loading", "lazy");
    expect("img").toHaveStyle({ "min-height": "1px" });
    advanceTime(6000);
    await def;
    expect("img").toHaveAttribute("src", "/web/image/website.library_image_08");
    expect("img").toHaveAttribute("loading", "lazy");
    expect("img").toHaveStyle({ "min-height": "100px" });
});
