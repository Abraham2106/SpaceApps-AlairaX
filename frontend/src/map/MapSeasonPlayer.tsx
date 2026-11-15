import { translate } from "../lib/i18n";
import { useEffect, useState, type ReactNode } from "react";
import { Pause, Play } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { useComparison } from "../data/queries";
import { useInstrument } from "../store";
import { hasDailyBalance, SEASON_MONTHS } from "../lib/season";
import { useRecentSeasons } from "../data/recent";
import type { Lang } from "../lib/types";
import { useMobileViewport } from "../lib/viewport";

const SEASON_DAYS = 274;
const STAGES = [
  { day: 0, label: "mapSeasonPlayer.windowStage" },
  { day: 44, label: "mapSeasonPlayer.riceStage" },
  { day: 197, label: "mapSeasonPlayer.cowpeaSorghumStage" },
  { day: 244, label: "mapSeasonPlayer.melonStage" },
] as const;
const STAGES_BY_DESCENDING_DAY = [...STAGES].reverse();

function stageAt(day: number, lang: Lang) {
  const hit = STAGES_BY_DESCENDING_DAY.find((stage) => day >= stage.day) ?? STAGES[0];
  return translate(lang, hit.label);
}

export function MapSeasonPlayer() {
  const lang = useInstrument((state) => state.lang);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const setYears = useInstrument((state) => state.setYears);
  const [day, setDay] = useState(44);
  const [playing, setPlaying] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [params] = useSearchParams();
  const mobile = useMobileViewport();
  const compare = useComparison().data?.compare;
  const recent = useRecentSeasons();
  const years = recent.data?.seasons.map(({ year }) => year).sort((a, b) => b - a) ?? [];
  const selectedYear = yearA !== null && years.includes(yearA) ? yearA : years[0];
  const dates = recent.data?.seasons.find(({ year }) => year === selectedYear)?.runs[0]?.daily_balance.map(({ date }) => date) ?? [];
  const lastDay = dates.length > 1 ? dates.length - 1 : SEASON_DAYS;
  const activeDay = Math.min(day, lastDay);
  const locale = lang === "es" ? "es-CR" : "en-US";
  const date = new Intl.DateTimeFormat(locale, {
    day: "numeric", month: "short", timeZone: "UTC",
  }).format(dates[activeDay] ? new Date(dates[activeDay]) : Date.UTC(2000, 3, activeDay + 1));
  const labels = new Intl.DateTimeFormat(locale, { month: "short", timeZone: "UTC" });
  const months = dates.length
    ? dates.flatMap((iso, index) => index === 0 || iso.endsWith("-01") ? [[index, labels.format(new Date(iso))] as const] : [])
    : SEASON_MONTHS.map(([offset, key]) => [offset, translate(lang, key)] as const);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setDay((current) => {
        if (current >= lastDay) {
          setPlaying(false);
          return lastDay;
        }
        return Math.min(lastDay, current + 4);
      });
    }, 160);
    return () => window.clearInterval(timer);
  }, [lastDay, playing]);

  return (
    <div className="hud bottom-hud">
      <div className="player">
        <button type="button" className="play" aria-pressed={playing} onClick={() => {
          if (activeDay >= lastDay) setDay(0);
          setPlaying((value) => !value);
        }}>{playing ? <Pause size={16} strokeWidth={1.5} aria-hidden /> : <Play size={16} strokeWidth={1.5} aria-hidden />} {playing ? (translate(lang, "mapSeasonPlayer.pause")) : translate(lang, "mapSeasonPlayer.play")}</button>
        <div className="scrub">
          <div className="scrub-stages" aria-hidden>
            {!dates.length && STAGES.map((stage) => (
              <i key={stage.day} style={{ left: `${(stage.day / SEASON_DAYS) * 100}%` }} title={translate(lang, stage.label)} />
            ))}
          </div>
          <input
            type="range"
            min={0}
            max={lastDay}
            value={activeDay}
            aria-valuetext={dates.length ? date : `${date} · ${stageAt(activeDay, lang)}`}
            aria-label={translate(lang, dates.length ? "mapSeasonPlayer.modeledSeason" : "mapSeasonPlayer.seasonAprilDecember")}
            onChange={(event) => {
              setPlaying(false);
              setDay(Number(event.target.value));
            }}
          />
          <div className="scrub-months" aria-hidden>
            {months.map(([at, month]) => (
              <span key={at} style={{ left: `${(at / lastDay) * 100}%` }}>{month}</span>
            ))}
          </div>
        </div>
        <p className="player-now">
          <span>{translate(lang, dates.length ? "mapSeasonPlayer.modeledSeason" : "mapSeasonPlayer.seasonAprilDecember")}</span>
          <strong>{date}</strong>
        </p>
        <button className="compare-years" type="button" disabled={!compare} aria-expanded={compareOpen && Boolean(compare)} aria-haspopup={mobile ? "dialog" : undefined} aria-controls={compareOpen && compare ? "compare-years" : undefined} onClick={() => setCompareOpen((value) => !value)}>
          {translate(lang, "common.compareYears")}
        </button>
      </div>
      {compareOpen && compare ? (
        <YearPanel mobile={mobile} lang={lang} onClose={() => setCompareOpen(false)}>
          <label>{translate(lang, "common.yearA")}
            <select value={yearA ?? ""} onChange={(event) => setYears(event.target.value ? Number(event.target.value) : null, yearB)}>
              <option value="">{translate(lang, "mapSeasonPlayer.choose")}</option>
              {years.map((year) => <option key={year} value={year}>{year}</option>)}
            </select>
          </label>
          <label>{translate(lang, "common.yearB")}
            <select value={yearB ?? ""} onChange={(event) => setYears(yearA, event.target.value ? Number(event.target.value) : null)}>
              <option value="">{translate(lang, "mapSeasonPlayer.choose")}</option>
              {years.map((year) => <option key={year} value={year}>{year}</option>)}
            </select>
          </label>
          {hasDailyBalance(compare) ? <p className="faint">{translate(lang, "mapSeasonPlayer.similarYearsUsedSimulation")}</p> : null}
          <Link className="year-results" to={{ pathname: "/temporada", search: params.toString() }}>
            {translate(lang, "mapSeasonPlayer.viewSeasonResults")}
          </Link>
        </YearPanel>
      ) : null}
    </div>
  );
}

function YearPanel({ mobile, lang, onClose, children }: {
  mobile: boolean;
  lang: Lang;
  onClose: () => void;
  children: ReactNode;
}) {
  const controls = <div className="year-pop" id="compare-years">{children}</div>;
  if (!mobile) return controls;
  return (
    <Dialog labelledBy="compare-years-title" onClose={onClose}>
      <h2 id="compare-years-title">{translate(lang, "common.compareYears")}</h2>
      {controls}
      <button type="button" onClick={onClose}>{translate(lang, "common.close")}</button>
    </Dialog>
  );
}
