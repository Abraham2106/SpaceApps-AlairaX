# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "marimo==0.25.2",
#   "xgboost==3.4.1",
#   "numpy>=1.26,<3",
#   "pandas>=2.1,<4",
#   "altair>=5,<7",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import importlib.util
    from datetime import date
    from pathlib import Path
    from shutil import make_archive

    import altair as alt
    import marimo as mo
    import pandas as pd

    return Path, alt, date, importlib, make_archive, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # NandaView · Validación por fecha

    **Lluvia:** estima el acumulado de los próximos siete días con datos POWER
    hasta el cierre de la fecha de corte.

    **Simulador:** aproxima el déficit hídrico de FAO-56 para escenarios completos.

    En Molab, activa **RTX PRO 6000 Blackwell** desde los recursos del notebook.
    Indica las rutas locales del script y el dataset. El botón inicia una sola
    corrida con límites de tiempo y rondas.
    """)
    return


@app.cell
def _(Path, mo):
    trainer_path = mo.ui.text(value="scripts/train_molab.py" if Path("scripts/train_molab.py").is_file()
                              else "train_molab.py", label="Ruta del script")
    default_data = "datasets/processed/features/guanacaste/regional-features.json"
    dataset = mo.ui.text(value=default_data if Path(default_data).is_file()
                         else "guanacaste-features.json", label="Dataset JSON")
    task = mo.ui.dropdown(["rainfall", "surrogate"], value="rainfall", label="Objetivo")
    validation = mo.ui.text(value="2018-01-01", label="Inicio de validación")
    test = mo.ui.text(value="2023-01-01", label="Inicio de prueba final")
    rounds = mo.ui.number(start=1, stop=3000, value=500, label="Máximo de rondas")
    seconds = mo.ui.number(start=5, stop=3600, value=600, label="Límite de entrenamiento (s)")
    tolerance = mo.ui.number(start=0, stop=1000, value=10, label="Tolerancia del error (mm)")
    run_training = mo.ui.run_button(label="Entrenar en Blackwell")
    controls = mo.ui.dictionary(dict(trainer=trainer_path, dataset=dataset, task=task,
        validation=validation, test=test, rounds=rounds, seconds=seconds, tolerance=tolerance
    )).form(submit_button_label="Aplicar configuración")
    mo.vstack([controls, run_training])
    return controls, run_training


@app.cell
def _(Path, controls, date, importlib, mo, run_training):
    mo.stop(not run_training.value or controls.value is None)
    # The uploaded trainer is code from this project. Its hash is saved in the run report.
    _config = controls.value
    _script = Path(_config["trainer"])
    _spec = importlib.util.spec_from_file_location("nandaview_trainer", _script)
    _trainer = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_trainer)
    run_dir, report, history = _trainer.train(
        _config["dataset"], "outputs/molab", task=_config["task"],
        validation_start=date.fromisoformat(_config["validation"]),
        test_start=date.fromisoformat(_config["test"]), rounds=int(_config["rounds"]),
        seconds=int(_config["seconds"]), tolerance=_config["tolerance"], device="cuda",
    )
    return history, report, run_dir


@app.cell
def _(Path, alt, history, make_archive, mo, pd, report, run_dir):
    _curve = pd.DataFrame({name: values["mae"] for name, values in history.items()})
    _curve.index += 1
    _curve.index.name = "ronda"
    _plot = alt.Chart(_curve.reset_index().melt("ronda", var_name="partición", value_name="MAE (mm)")).mark_line().encode(
        x="ronda:Q", y="MAE (mm):Q", color="partición:N",
    )
    _selected = alt.Chart(pd.DataFrame({"ronda": [report["best_round"]]})).mark_rule(strokeDash=[4, 4]).encode(x="ronda:Q")
    _hits = pd.DataFrame({"ronda": _curve.index,
                         "dentro de tolerancia (%)": history["validation"]["within_tolerance_pct"]})
    _hits_chart = alt.Chart(_hits).mark_line().encode(
        x="ronda:Q", y=alt.Y("dentro de tolerancia (%):Q", scale=alt.Scale(domain=[0, 100])),
    )
    _zip = Path(make_archive(str(run_dir), "zip", root_dir=run_dir))
    mo.vstack([
        mo.md(f"**Ronda seleccionada por validación:** {report['best_round']}"),
        _plot + _selected,
        mo.md(f"**Validación dentro de ±{report['tolerance']:g} mm**"),
        _hits_chart + _selected,
        mo.ui.table(pd.DataFrame([report["test"], report["baseline"]], index=["XGBoost", "Referencia"])),
        mo.ui.table(pd.DataFrame.from_dict(report["test_by_year"], orient="index")),
        mo.download(_zip.read_bytes(), filename=_zip.name, label="Descargar modelo y resultados"),
    ])
    return


if __name__ == "__main__":
    app.run()
