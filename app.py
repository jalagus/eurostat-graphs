import pathlib
import pickle
import eurostat
import asyncio

import pandas as pd
from shiny import ui, App
from shinywidgets import output_widget, render_widget
import plotly.express as px


def filter_data(full_data: pd.DataFrame, filters: dict):
    filtered_data = full_data
    for filter_key, filter_value in filters.items():
        filtered_data = filtered_data[filtered_data[filter_key] == filter_value]
    return filtered_data


def get_eurostat_data(cache_path: pathlib.Path = pathlib.Path("data.cache")):
    eurostat_code = "GOV_10A_EXP"

    if cache_path.exists():
        with cache_path.open("rb") as fp:
            full_data, cat_titles_dict, geo_titles_dict = pickle.load(fp)
    else:
        data = eurostat.get_data(eurostat_code)

        cat_titles = eurostat.get_dic(eurostat_code, "cofog99")
        cat_titles_dict = {x[0]: x[1] for x in cat_titles}

        geo_titles = eurostat.get_dic(eurostat_code, "geo")
        geo_titles_dict = {x[0]: x[1] for x in geo_titles}

        full_data = pd.DataFrame.from_records(data[1:], columns=data[0])
        full_data["country"] = full_data["geo\TIME_PERIOD"].apply(
            lambda x: geo_titles_dict[x]
        )
        full_data["category"] = full_data["cofog99"].apply(lambda x: cat_titles_dict[x])

        with cache_path.open("wb") as fp:
            pickle.dump([full_data, cat_titles_dict, geo_titles_dict], fp)

    return full_data, cat_titles_dict, geo_titles_dict


full_data, cat_titles_dict, geo_titles_dict = get_eurostat_data()
filtered_data = filter_data(
    full_data, {"sector": "S13", "unit": "PC_GDP", "na_item": "TE"}
)

uniq_countries = full_data["geo\TIME_PERIOD"].unique().tolist()
geo_titles_dict = {
    k: v
    for k, v in sorted(geo_titles_dict.items(), key=lambda x: x[1])
    if k in uniq_countries
}
cat_titles_dict = {k: v for k, v in sorted(cat_titles_dict.items(), key=lambda x: x[1])}

home_tab = ui.nav("About",
    ui.panel_title("Welcome to Eurostat visualizer"), 
)

budget_tab = ui.nav("Budget comparisons",
    ui.panel_title("Budget comparisons by country"),
    ui.layout_sidebar(
        ui.panel_sidebar(
            ui.input_slider(
                "year",
                "Choose a year:",
                2000,
                2021,
                2021,
                sep="",
                animate=ui.AnimationOptions(interval=1000, loop=False),
            ),
            ui.input_select(
                "plot_cat_code",
                label="Category",
                choices={k: v for k, v in cat_titles_dict.items() if len(k) < 5},
                multiple=True,
                size=7
            ),
            ui.input_select(
                "country", label="Country", choices=geo_titles_dict, multiple=True, size=7
            ),
            ui.download_button("download_data", "Download data", class_="btn-primary"),
            ui.div(
                ui.span("Data source: "), 
                ui.a("Eurostat", href_="https://ec.europa.eu/eurostat", target_="_blank")
            ),
        ),
        ui.panel_main(output_widget("my_widget")),
    ),
)

app_ui = ui.page_fluid(
    ui.navset_tab_card(
        home_tab,
        budget_tab
    ),
    ui.div("COPYRIGHT © 2023 JARKKO LAGUS - ALL RIGHTS RESERVED"),
)


def server(input, output, session):
    @output
    @render_widget
    def my_widget():
        if len(input.country()) < 1 or len(input.plot_cat_code()) < 1:
            return None

        plot_data = filtered_data[
            filtered_data["geo\TIME_PERIOD"]
            .apply(lambda x: x in input.country())
            .tolist()
        ]
        plot_data = plot_data[
            plot_data["cofog99"].apply(lambda x: x in input.plot_cat_code()).tolist()
        ]
        plot_data["value"] = plot_data[str(input.year())] / 100

        fig = px.bar(
            plot_data,
            x="value",
            y="category",
            color="country",
            text_auto=".2%",
            title=f"Budget as a percentage of GDP ({input.year()})",
            barmode="group",
            labels={"category": "", "value": "% GDP", "country": "Country"},
        )
        fig.update_xaxes(tickformat=".2%")
        fig.update_layout(
            font={"size": 15}
        )
        fig.layout.height = 220 + len(input.plot_cat_code()) * (len(input.country()) * 30)
        return fig

    @session.download(filename=lambda: f"data.csv")
    async def download_data():
        plot_data = filtered_data[
            filtered_data["geo\TIME_PERIOD"]
            .apply(lambda x: x in input.country())
            .tolist()
        ]
        plot_data = plot_data[
            plot_data["cofog99"].apply(lambda x: x in input.plot_cat_code()).tolist()
        ]
        await asyncio.sleep(0.25)

        csv_rows = plot_data.to_csv()
        yield csv_rows


app = App(app_ui, server)
