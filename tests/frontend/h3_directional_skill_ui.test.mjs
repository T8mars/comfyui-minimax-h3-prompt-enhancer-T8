import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { addQualityUI, qualityLabel, creationLabel } from "../../web/js/h3_quality_ui.mjs";
import * as widgetState from "../../web/js/widget_state.mjs";
import {
    DIRECTIONAL_HELP_HEIGHT,
    DIRECTIONAL_SKILLS,
    addDirectionalSkillUI,
    directionalSkillDescription,
    directionalSkillId,
    directionalSkillLabel,
    isDirectionalSkillEnabled,
} from "../../web/js/h3_directional_skill_ui.mjs";

test("directional choices round-trip stable IDs and retain each model's format ownership", () => {
    for (const skill of DIRECTIONAL_SKILLS) {
        assert.equal(directionalSkillId(skill.label), skill.id);
        assert.equal(directionalSkillLabel(skill.id), skill.label);
    }
    for (const empty of [undefined, null, "", " \t\n"]) {
        assert.equal(directionalSkillId(empty), "none");
        assert.equal(directionalSkillLabel(empty), "关闭 / Off");
    }
    assert.equal(isDirectionalSkillEnabled("关闭 / Off"), false);
    assert.match(directionalSkillDescription("cinematic_gunfight"), /H3 官方核心/);
    const seedance = directionalSkillDescription("cinematic_gunfight", "seedance20");
    assert.match(seedance, /Seedance 原有格式保留/);
    assert.doesNotMatch(seedance, /H3/);
    for (const skill of DIRECTIONAL_SKILLS.slice(1)) {
        const lines = directionalSkillDescription(skill.id).split("\n");
        assert.match(lines[1], /^例 \/ Example:/, "example is immediately visible below the selected source");
        assert.match(lines[1], /[\u4e00-\u9fff]/);
        assert.match(lines[1], /[A-Za-z]{3}/);
    }
});

test("author labels migrate legacy saved labels without changing IDs or workflow fields", async () => {
    for (const [filename, target] of [["minimax_h3_prompt_enhancer.js", "h3"], ["seedance20_prompt_enhancer.js", "seedance20"]]) {
        const harness = await enhancerHarness(filename, target);
        for (const skill of DIRECTIONAL_SKILLS.filter((item) => item.legacyLabel)) {
            assert.equal(directionalSkillId(skill.legacyLabel), skill.id);
            assert.equal(directionalSkillLabel(skill.legacyLabel), skill.label);
            const saved = sampleValues(harness.names);
            saved[35] = skill.legacyLabel;
            const node = harness.configure(saved);
            const values = harness.values(node);
            assert.equal(values.director_skill, skill.label);
            assert.equal(values.seed, 42);
            assert.equal(values.local_model, "test-model.gguf");
            assert.equal(values.case_template, "saved case_template");
            const serialized = {};
            node.onSerialize(serialized);
            assert.equal(serialized.widgets_values.length, 38);
            assert.equal(serialized.widgets_values[35], skill.id);
            const restored = harness.values(harness.configure(serialized.widgets_values));
            assert.equal(restored.director_skill, skill.label);
        }
    }
});

test("conditional authoring choices round-trip all 38 fields through the real enhancer hooks", async () => {
    for (const [filename, target] of [["minimax_h3_prompt_enhancer.js", "h3"], ["seedance20_prompt_enhancer.js", "seedance20"]]) {
        const harness = await enhancerHarness(filename, target);
        for (const id of ["drama_scene", "situational_drama", "zhenzhen_pov"]) {
            const saved = sampleValues(harness.names);
            saved[35] = id;
            const node = harness.configure(saved);
            const values = harness.values(node);
            assert.equal(values.director_skill, directionalSkillLabel(id));
            assert.equal(values.seed, 42);
            assert.equal(values.local_model, "test-model.gguf");
            assert.equal(values.case_template, "saved case_template");
            const serialized = {};
            node.onSerialize(serialized);
            assert.equal(serialized.widgets_values.length, 38);
            assert.equal(serialized.widgets_values[35], id);
            assert.deepEqual(harness.values(harness.configure(serialized.widgets_values)), values);
            const help = directionalSkillDescription(id, target);
            assert.match(help, /明确要求/);
            assert.match(help, /explicit/i);
            if (target === "seedance20") assert.doesNotMatch(help, /H3/);
        }
    }
});

test("POV examples and 36-field saves reload with the actual reordered widgets", async () => {
    for (const [filename, target, type] of [
        ["minimax_h3_prompt_enhancer.js", "h3", "MiniMaxH3PromptEnhancerT8"],
        ["seedance20_prompt_enhancer.js", "seedance20", "Seedance20PromptEnhancerT8"],
    ]) {
        const harness = await enhancerHarness(filename, target);
        const workflow = JSON.parse(await readFile(new URL(`../../example_workflows/directional_zhenzhen_pov_${target}.json`, import.meta.url), "utf8"));
        const original = workflow.nodes.find(n => n.type === type).widgets_values;
        for (const saved of [original, original.slice(0, 36)]) {
            const node = harness.configure([...saved]);
            const values = harness.values(node);
            assert.equal(values.director_skill, directionalSkillLabel("zhenzhen_pov"));
            harness.names.slice(0, saved.length).forEach((name, index) => {
                const expected = name === "quality_mode" ? qualityLabel(saved[index])
                    : name === "creation_mode" ? creationLabel(saved[index]) : saved[index];
                if (name !== "director_skill") assert.equal(values[name], expected, name);
            });
            const serialized = {};
            node.onSerialize(serialized);
            assert.equal(serialized.widgets_values.length, 38);
            assert.equal(serialized.widgets_values[35], "zhenzhen_pov");
            assert.deepEqual(harness.values(harness.configure(serialized.widgets_values)), values);
        }
        const help = directionalSkillDescription("zhenzhen_pov", target);
        assert.match(help, /不锁人物或渠道/);
        assert.match(help, /明确要求/);
        assert.doesNotMatch(help, /mpov/);
    }
});

test("wushu examples retain 38 named fields and 36-field saves through real enhancer hooks", async () => {
    for (const [filename, target, type] of [
        ["minimax_h3_prompt_enhancer.js", "h3", "MiniMaxH3PromptEnhancerT8"],
        ["seedance20_prompt_enhancer.js", "seedance20", "Seedance20PromptEnhancerT8"],
    ]) {
        const harness = await enhancerHarness(filename, target);
        const graph = JSON.parse(await readFile(new URL(`../../example_workflows/directional_wushu_combat_${target}.json`, import.meta.url), "utf8"));
        const original = graph.nodes.find(n => n.type === type).widgets_values;
        assert.equal(original.length, 38);
        assert.equal(original[35], "wushu_combat");
        assert.equal(original[36], "check");
        assert.equal(original[37], "off");
        for (const saved of [original, original.slice(0, 36)]) {
            const node = harness.configure([...saved]);
            const values = harness.values(node);
            assert.equal(values.director_skill, directionalSkillLabel("wushu_combat"));
            harness.names.slice(0, saved.length).forEach((name, index) => {
                const expected = name === "director_skill" ? directionalSkillLabel(saved[index])
                    : name === "quality_mode" ? qualityLabel(saved[index])
                    : name === "creation_mode" ? creationLabel(saved[index]) : saved[index];
                assert.equal(values[name], expected, name);
            });
            const serialized = {};
            node.onSerialize(serialized);
            assert.equal(serialized.widgets_values.length, 38);
            assert.equal(serialized.widgets_values[35], "wushu_combat");
            assert.deepEqual(harness.values(harness.configure(serialized.widgets_values)), values);
        }
        const help = directionalSkillDescription("wushu_combat", target);
        assert.match(help, /Jojocodex/);
        assert.match(help, /跨镜继承/);
        assert.match(help, /no forced damage/);
        assert.doesNotMatch(help, /new dialogue needs/);
        if (target === "seedance20") assert.doesNotMatch(help, /H3/);
    }
});

test("unknown IDs are preserved for validation without activating a skill or exposing the value in help", () => {
    for (const invalid of [0, false, [], {}]) {
        assert.equal(directionalSkillId(invalid), invalid);
        assert.equal(directionalSkillLabel(invalid), invalid);
        assert.equal(isDirectionalSkillEnabled(invalid), false);
        assert.match(directionalSkillDescription(invalid), /^未知定向技能，请重新选择/);
    }
    for (const unknown of ["future_skill", "  future_skill  ", "sk-test-private-value"]) {
        assert.equal(directionalSkillId(unknown), unknown);
        assert.equal(directionalSkillLabel(unknown), unknown);
        assert.equal(isDirectionalSkillEnabled(unknown), false);
        for (const target of ["h3", "seedance20"]) {
            const help = directionalSkillDescription(unknown, target);
            assert.match(help, /^未知定向技能，请重新选择/);
            assert.ok(!help.includes(unknown.trim()));
            assert.doesNotMatch(help, /定向创作：关闭|当前创作来源/);
        }
    }
});

test("20 skill/off cycles retain saved templates and fixed geometry without extra widgets", () => {
    const originalDocument = globalThis.document;
    const originalRaf = globalThis.requestAnimationFrame;
    globalThis.document = { createElement: () => ({ style: {}, setAttribute() {}, textContent: "" }) };
    globalThis.requestAnimationFrame = () => { throw new Error("directional helper must not schedule animation frames"); };
    try {
        const saved = { case_template: "case-a", prompt_mode: "参考模板融合", reference_template: "manual original" };
        const widgets = Object.entries(saved).map(([name, value]) => ({ name, value, label: name, tooltip: `original ${name}` }));
        const skill = { name: "director_skill", value: "none" };
        widgets.push(skill);
        let changes = 0;
        const node = {
            widgets,
            graph: { change() { changes++; } },
            setDirtyCanvas() {},
            addDOMWidget(name, type, element, options) {
                const widget = { name, type, element, options };
                this.widgets.push(widget);
                return widget;
            },
        };
        const detail = addDirectionalSkillUI(node, skill);
        assert.equal(node.widgets[1], skill);
        assert.equal(node.widgets[2], detail);
        const baselineLength = node.widgets.length;
        for (let i = 0; i < 20; i++) {
            skill.value = DIRECTIONAL_SKILLS[1 + i % (DIRECTIONAL_SKILLS.length - 1)].id;
            skill.callback();
            for (const [name, value] of Object.entries(saved)) {
                const widget = node.widgets.find((item) => item.name === name);
                assert.equal(widget.value, value);
                assert.match(widget.label, /当前暂停/);
            }
            assert.match(detail.element.textContent, /关闭后恢复/);
            skill.value = "none";
            skill.callback();
            assert.equal(detail.options.getMinHeight(), DIRECTIONAL_HELP_HEIGHT);
            assert.equal(detail.options.getMaxHeight(), DIRECTIONAL_HELP_HEIGHT);
            assert.equal(detail.options.getHeight(), DIRECTIONAL_HELP_HEIGHT);
            assert.equal(detail.options.margin, 0);
            assert.equal(detail.options.getMinHeight() - 2 * detail.options.margin, DIRECTIONAL_HELP_HEIGHT);
            assert.deepEqual(detail.computeSize(), [0, DIRECTIONAL_HELP_HEIGHT]);
            assert.equal(node.widgets.length, baselineLength);
            for (const [name, value] of Object.entries(saved)) {
                const widget = node.widgets.find((item) => item.name === name);
                assert.equal(widget.value, value);
                assert.equal(widget.label, name);
                assert.equal(widget.tooltip, `original ${name}`);
            }
        }
        assert.equal(changes, 40);
        skill.value = "sk-test-private-value";
        skill.callback();
        assert.equal(skill.value, "sk-test-private-value");
        assert.match(detail.element.textContent, /^未知定向技能，请重新选择/);
        assert.doesNotMatch(detail.element.textContent, /sk-test-private-value/);
        assert.equal(node.widgets.find((item) => item.name === "case_template").label, "case_template");
        assert.equal(detail.serializeValue(), undefined);
        assert.equal(addDirectionalSkillUI(node, skill), detail);
        assert.equal(node.widgets.length, baselineLength);
    } finally {
        globalThis.document = originalDocument;
        globalThis.requestAnimationFrame = originalRaf;
    }
});

// Run the actual registration/configure/serialize hooks with only ComfyUI's
// host/import boundaries stubbed. This tests migrations, not a copied algorithm.
async function enhancerHarness(filename, target) {
    const source = await readFile(new URL(`../../web/js/${filename}`, import.meta.url), "utf8");
    const frames = [];
    let extension;
    const context = vm.createContext({
        ...widgetState,
        addDirectionalSkillUI,
        addQualityUI, qualityLabel, creationLabel,
        directionalSkillId,
        directionalSkillLabel,
        isDirectionalSkillEnabled,
        serializedCaseTemplateValue: (_node, widget) => widget?.value,
        app: { registerExtension(value) { extension = value; } },
        requestAnimationFrame(callback) { frames.push(callback); },
    });
    const noImports = source.replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*$/gm, "")
        .replace(/^export\s+/gm, "").replaceAll("import.meta.url", '"https://example.test/extension.js"');
    const extra = target === "seedance20"
        ? ", published: PUBLISHED_WIDGET_NAMES, publishedV1: PUBLISHED_V1_WIDGET_NAMES, runtimeV1: RUNTIME_V1_WIDGET_NAMES"
        : "";
    vm.runInContext(`${noImports}\nglobalThis.fixture = { names: SERIALIZED_WIDGET_NAMES, defaults: LOCAL_WIDGET_DEFAULTS${extra} };`, context);
    const names = [...context.fixture.names];
    class TestNode {
        constructor() {
            this.widgets = names.map((name) => ({ name, value: `not restored ${name}` }));
            // Reproduce the native UI's positional configure after the director
            // widget was moved beside templates. Named restoration must fix it.
            const director = this.widgets.find((w) => w.name === "director_skill");
            if (director) {
                this.widgets.splice(this.widgets.indexOf(director), 1);
                this.widgets.splice(this.widgets.findIndex((widget) => widget.name === "case_template") + 1, 0, director);
            } else {
                const model = this.widgets.find((widget) => widget.name === "local_model");
                this.widgets.splice(this.widgets.indexOf(model), 1);
                this.widgets.splice(1, 0, model);
            }
            this.properties = {};
            this.t8NormalizePromptOptions = this.s20NormalizeOptions = () => {
                director.value = directionalSkillLabel(director.value);
            };
            this.t8RestoreCaseTemplate = (value) => { this.widgets.find((widget) => widget.name === "case_template").value = value; };
        }
        onConfigure(data) {
            this.received = [...data.widgets_values];
            data.widgets_values.forEach((value, index) => { if (this.widgets[index]) this.widgets[index].value = value; });
        }
    }
    await extension.beforeRegisterNodeDef(TestNode, { name: target === "h3" ? "MiniMaxH3PromptEnhancerT8"
        : target === "music3" ? "MiniMaxMusic3PromptEnhancerT8" : "Seedance20PromptEnhancerT8" });
    return {
        names,
        defaults: context.fixture.defaults,
        fixture: context.fixture,
        configure(values, { beforeFrames } = {}) {
            const node = new TestNode();
            node.onConfigure({ widgets_values: values });
            beforeFrames?.(node);
            let limit = 10;
            while (frames.length && limit-- > 0) frames.shift()();
            assert.equal(frames.length, 0, "configure animation work must be bounded");
            return node;
        },
        values(node) { return Object.fromEntries(node.widgets.map((widget) => [widget.name, widget.value])); },
    };
}

test("H3, Seedance and Music restore models synchronously before missing-model scan (#20)", async () => {
    for (const [filename, target] of [["minimax_h3_prompt_enhancer.js", "h3"],
        ["seedance20_prompt_enhancer.js", "seedance20"], ["music3_prompt_enhancer.js", "music3"]]) {
        const harness = await enhancerHarness(filename, target);
        const saved = sampleValues(harness.names);
        saved[harness.names.indexOf("api_mode")] = "本地 GGUF（llama.cpp / Qwen，离线）";
        const restored = harness.configure(saved, { beforeFrames(node) {
            const values = harness.values(node);
            for (const name of ["api_mode", "seed", "local_model", "local_mmproj"]) {
                if (harness.names.includes(name)) assert.equal(values[name], saved[harness.names.indexOf(name)], `${target}: ${name} before RAF`);
            }
            for (const widget of node.widgets) {
                if (typeof widget.value === "string" && widget.value.endsWith(".gguf")) {
                    assert.ok(["local_model", "local_mmproj"].includes(widget.name), `${target}: false missing-model candidate ${widget.name}`);
                }
            }
        } });
        const serialized = {};
        restored.onSerialize(serialized);
        assert.deepEqual(Object.keys(serialized.widgets_values_named), harness.names, `${target}: native named fields`);
        harness.names.forEach((name, index) => assert.equal(serialized.widgets_values_named[name],
            serialized.widgets_values[index], `${target}: ${name} in both serialized forms`));
    }
});

function sampleValues(names) {
    const concrete = {
        api_mode: "OpenAI兼容接口（备用）",
        custom_model: "vendor/my-model",
        openai_base_url: "https://example.test/v1",
        custom_length_target: 333,
        seed: 42,
        control_after_generate: "randomize",
        local_model: "test-model.gguf",
        local_mmproj: "test-projector.gguf",
        relay_time_ranges: "0-2\n2-5",
        director_skill: "cinematic_gunfight",
    };
    return names.map((name) => concrete[name] ?? `saved ${name}`);
}

test("all shipped H3/Seedance workflows retain native widget positions with optional combat camera socket", async () => {
    const directory = new URL("../../example_workflows/", import.meta.url);
    const harnesses = {
        MiniMaxH3PromptEnhancerT8: await enhancerHarness("minimax_h3_prompt_enhancer.js", "h3"),
        Seedance20PromptEnhancerT8: await enhancerHarness("seedance20_prompt_enhancer.js", "seedance20"),
    };
    let cameraExamples = 0;
    let checked = 0;
    for (const filename of (await readdir(directory)).filter(name => name.endsWith(".json"))) {
        const graph = JSON.parse(await readFile(new URL(filename, directory), "utf8"));
        for (const saved of graph.nodes || []) {
            const harness = harnesses[saved.type];
            if (!harness) continue;
            checked++;
            const node = harness.configure([...saved.widgets_values]);
            const first = harness.values(node);
            const serialized = {};
            node.onSerialize(serialized);
            assert.equal(serialized.widgets_values.length, 38, filename);
            assert.deepEqual(harness.values(harness.configure(serialized.widgets_values)), first, filename);
            assert.ok(!harness.names.includes("combat_camera_config"));
            if (saved.inputs.some(input => input.name === "combat_camera_config")) {
                cameraExamples++;
                assert.equal(saved.inputs.at(-1).name, "combat_camera_config");
                assert.equal(saved.widgets_values.length, 38);
                assert.equal(serialized.widgets_values[0], saved.widgets_values[0]);
                assert.equal(first.api_mode, "贞贞平价小屋（推荐）");
                assert.equal(first.control_after_generate, "fixed");
                assert.equal(serialized.widgets_values[35], "none");
                assert.deepEqual(graph.nodes.find(n => n.type === "T8CombatCameraConfig").widgets_values,
                    ["强化（明确轨迹与落点）", "沿用原设定 / Follow", "写实 / Natural"]);
            }
        }
    }
    assert.equal(cameraExamples, 2);
    assert.ok(checked >= 20);
});

test("H3 22/31/35/36 workflows preserve every field and fill only appended defaults", async () => {
    const harness = await enhancerHarness("minimax_h3_prompt_enhancer.js", "h3");
    assert.equal(harness.names.length, 38);
    assert.equal(harness.names[35], "director_skill");
    for (const length of [22, 31, 35, 36]) {
        const saved = sampleValues(harness.names.slice(0, length));
        const before = [...saved];
        const node = harness.configure(saved);
        const restored = harness.values(node);
        harness.names.slice(0, length).forEach((name, index) => assert.equal(restored[name], name === "director_skill" ? directionalSkillLabel(saved[index]) : saved[index], name));
        harness.names.slice(length).forEach((name) => assert.equal(restored[name], harness.defaults[name], name));
        assert.equal(restored.director_skill, length === 36 ? directionalSkillLabel("cinematic_gunfight") : "关闭 / Off");
        assert.deepEqual(saved, before, "migration must not mutate source workflow");
    }
});

test("H3 older 16/17/19/21 layouts still migrate before the appended skill", async () => {
    const harness = await enhancerHarness("minimax_h3_prompt_enhancer.js", "h3");
    const layouts = new Map([[22, harness.names.slice(0, 22)]]);
    const n21 = [...layouts.get(22)]; n21.splice(10, 1); layouts.set(21, n21);
    const n19 = [...n21]; n19.splice(11, 2); layouts.set(19, n19);
    const n17 = [...n19]; n17.splice(8, 2); layouts.set(17, n17);
    const n16 = [...n17]; n16.splice(3, 1); layouts.set(16, n16);
    for (const length of [16, 17, 19, 21]) {
        const names = layouts.get(length);
        const saved = sampleValues(names);
        const restored = harness.values(harness.configure(saved));
        names.forEach((name, index) => assert.equal(restored[name], saved[index], name));
        assert.equal(restored.director_skill, "关闭 / Off");
        assert.equal(restored.local_model, harness.defaults.local_model);
    }
});

test("Seedance 26/35 published and runtime layouts preserve INT and provider positions", async () => {
    const harness = await enhancerHarness("seedance20_prompt_enhancer.js", "seedance20");
    assert.equal(harness.names.length, 38);
    assert.equal(harness.names[35], "director_skill");
    for (const layout of [harness.fixture.publishedV1, harness.fixture.runtimeV1, harness.fixture.published, harness.names.slice(0, 35)]) {
        const names = [...layout];
        const saved = sampleValues(names);
        const restored = harness.values(harness.configure(saved));
        names.forEach((name, index) => assert.equal(restored[name], saved[index], name));
        assert.equal(restored.custom_length_target, 333);
        assert.equal(restored.director_skill, "关闭 / Off");
    }
    const old36 = harness.values(harness.configure(sampleValues(harness.names.slice(0, 36))));
    assert.equal(old36.director_skill, directionalSkillLabel("cinematic_gunfight"));
    assert.equal(old36.quality_mode, harness.defaults.quality_mode);
    assert.equal(old36.creation_mode, harness.defaults.creation_mode);
});

test("Seedance 23/25 legacy workflows still keep their original values", async () => {
    const harness = await enhancerHarness("seedance20_prompt_enhancer.js", "seedance20");
    const n25 = [...harness.fixture.publishedV1]; n25.splice(9, 1);
    const n23 = [...n25]; n23.splice(19, 2);
    for (const names of [n23, n25]) {
        const saved = sampleValues(names);
        const restored = harness.values(harness.configure(saved));
        names.forEach((name, index) => assert.equal(restored[name], saved[index], name));
        assert.equal(restored.director_skill, "关闭 / Off");
        assert.equal(restored.local_model, harness.defaults.local_model);
    }
});

test("both current workflows serialize stable skill IDs and reload without shifting seed or models", async () => {
    for (const [filename, target] of [["minimax_h3_prompt_enhancer.js", "h3"], ["seedance20_prompt_enhancer.js", "seedance20"]]) {
        const harness = await enhancerHarness(filename, target);
        const saved = sampleValues(harness.names);
        const node = harness.configure(saved);
        const restored = harness.values(node);
        assert.equal(restored.director_skill, directionalSkillLabel("cinematic_gunfight"));
        const serialized = {};
        node.onSerialize(serialized);
        assert.equal(serialized.widgets_values.length, 38);
        assert.equal(serialized.widgets_values[35], "cinematic_gunfight");
        const again = harness.values(harness.configure([...serialized.widgets_values]));
        assert.equal(again.seed, 42);
        assert.equal(again.control_after_generate, "randomize");
        assert.equal(again.local_model, "test-model.gguf");
        assert.equal(again.custom_model, "vendor/my-model");
        assert.equal(again.director_skill, restored.director_skill);
    }
});

test("Ning round-trips through both enhancer hooks without changing the 38-value layout", async () => {
    for (const [filename, target] of [["minimax_h3_prompt_enhancer.js", "h3"], ["seedance20_prompt_enhancer.js", "seedance20"]]) {
        const harness = await enhancerHarness(filename, target);
        for (const length of [36, 38]) {
            const saved = sampleValues(harness.names.slice(0, length));
            saved[35] = "ning_wenwu";
            const node = harness.configure(saved);
            assert.equal(harness.values(node).director_skill, directionalSkillLabel("ning_wenwu"));
            const serialized = {};
            node.onSerialize(serialized);
            assert.equal(serialized.widgets_values.length, 38);
            assert.equal(serialized.widgets_values[35], "ning_wenwu");
            const restored = harness.values(harness.configure(serialized.widgets_values));
            assert.equal(restored.director_skill, directionalSkillLabel("ning_wenwu"));
            assert.equal(restored.seed, 42);
            assert.equal(restored.local_model, "test-model.gguf");
            assert.equal(restored.case_template, "saved case_template");
        }
    }
});

test("both enhancers preserve unknown skill IDs through real configure and serialize hooks", async () => {
    for (const [filename, target] of [["minimax_h3_prompt_enhancer.js", "h3"], ["seedance20_prompt_enhancer.js", "seedance20"]]) {
        const harness = await enhancerHarness(filename, target);
        for (const unknown of ["future_skill", "sk-test-private-value"]) {
            const saved = sampleValues(harness.names);
            saved[35] = unknown;
            const node = harness.configure(saved);
            assert.equal(harness.values(node).director_skill, unknown);
            const serialized = {};
            node.onSerialize(serialized);
            assert.equal(serialized.widgets_values[35], unknown);
            const restored = harness.values(harness.configure([...serialized.widgets_values]));
            assert.equal(restored.director_skill, unknown);
            assert.equal(restored.seed, 42);
            assert.equal(restored.local_model, "test-model.gguf");
            assert.equal(restored.case_template, "saved case_template");
        }
    }
});
