"use strict";

import powerbi from "powerbi-visuals-api";
import * as d3 from "d3";
import "./../style/visual.less";

import VisualConstructorOptions = powerbi.extensibility.visual.VisualConstructorOptions;
import VisualUpdateOptions = powerbi.extensibility.visual.VisualUpdateOptions;
import IVisual = powerbi.extensibility.visual.IVisual;

// TODO: Replace with your style guide colors
const COLORS = {
    primary: "#0078D4",
    secondary: "#E66C37",
    background: "#FFFFFF",
    text: "#1F1F1F",
    grid: "#E8E8E8",
};

export class Visual implements IVisual {
    private svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
    private container: d3.Selection<SVGGElement, unknown, null, undefined>;

    constructor(options: VisualConstructorOptions) {
        const element = options.element;
        element.style.backgroundColor = COLORS.background;
        element.style.overflow = "hidden";

        this.svg = d3.select(element)
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100%");

        this.container = this.svg.append("g");
    }

    public update(options: VisualUpdateOptions) {
        const dataView = options.dataViews?.[0];
        if (!dataView?.categorical?.categories?.length) {
            this.container.selectAll("*").remove();
            return;
        }

        const width = options.viewport.width;
        const height = options.viewport.height;
        this.svg.attr("viewBox", `0 0 ${width} ${height}`);

        const categories = dataView.categorical.categories[0].values;
        const values = dataView.categorical.values?.[0]?.values || [];

        // TODO: Replace this with your visualization logic
        this.container.selectAll("*").remove();

        const barHeight = Math.min(30, (height - 40) / categories.length);
        const maxVal = Math.max(...values.map(v => Number(v) || 0), 1);
        const xScale = d3.scaleLinear().domain([0, maxVal]).range([0, width - 120]);

        const bars = this.container.selectAll("g.bar")
            .data(categories)
            .join("g")
            .attr("class", "bar")
            .attr("transform", (_, i) => `translate(100, ${20 + i * (barHeight + 4)})`);

        bars.append("rect")
            .attr("width", (_, i) => xScale(Number(values[i]) || 0))
            .attr("height", barHeight)
            .attr("fill", COLORS.primary)
            .attr("rx", 4);

        bars.append("text")
            .attr("x", -6)
            .attr("y", barHeight / 2)
            .attr("text-anchor", "end")
            .attr("dominant-baseline", "middle")
            .attr("font-size", "10px")
            .attr("font-family", "Segoe UI, sans-serif")
            .attr("fill", COLORS.text)
            .text((d) => String(d).substring(0, 16));
    }

    public getFormattingModel(): powerbi.visuals.FormattingModel {
        return { cards: [] };
    }
}
