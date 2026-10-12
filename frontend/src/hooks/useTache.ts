import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { messageErreur } from "../api/client";
import type { SimulationTask } from "../types";

export type EtatTache = "idle" | "running" | "done" | "error";

interface Options<S extends SimulationTask, R> {
  statut: (taskId: string) => Promise<S>;
  resultat: (taskId: string) => Promise<R>;
  intervalle?: number;
  /** Clé de sessionStorage : la tâche est retrouvée après un rechargement de la page. */
  memoriser?: string;
}

const lireCle = (cle?: string) => {
  try { return cle ? sessionStorage.getItem(cle) : null; } catch { return null; }
};
const ecrireCle = (cle: string | undefined, v: string | null) => {
  if (!cle) return;
  try { if (v) sessionStorage.setItem(cle, v); else sessionStorage.removeItem(cle); } catch { /* stockage indisponible */ }
};

/** Lance une tâche de fond de l'API puis suit sa progression jusqu'au résultat. */
export function useTache<S extends SimulationTask, R>({ statut, resultat, intervalle = 700, memoriser }: Options<S, R>) {
  const memo = lireCle(memoriser);
  const [etat, setEtat] = useState<EtatTache>(memo ? "running" : "idle");
  const [suivi, setSuivi] = useState<S | null>(null);
  const [res, setRes] = useState<R | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(memo);
  const fns = useRef({ statut, resultat });
  fns.current = { statut, resultat };

  useEffect(() => {
    if (!taskId || etat !== "running") return;
    let actif = true;
    let timer: ReturnType<typeof setTimeout>;
    const suivre = async () => {
      try {
        const t = await fns.current.statut(taskId);
        if (!actif) return;
        setSuivi(t);
        if (t.status === "done") {
          const r = await fns.current.resultat(taskId);
          if (!actif) return;
          setRes(r);
          setEtat("done");
          return;
        }
        if (t.status === "error") {
          setErreur(t.error ?? "Erreur de calcul");
          setEtat("error");
          return;
        }
      } catch (e) {
        if (axios.isAxiosError(e) && e.response?.status === 404) {
          // tâche oubliée par le serveur (redémarrage) : on revient à l'état initial
          ecrireCle(memoriser, null);
          if (actif) { setTaskId(null); setEtat("idle"); }
          return;
        }
        /* erreur réseau passagère : on réessaie */
      }
      timer = setTimeout(suivre, intervalle);
    };
    suivre();
    return () => { actif = false; clearTimeout(timer); };
  }, [taskId, etat, intervalle, memoriser]);

  const lancer = useCallback(async (demarrer: () => Promise<S>) => {
    setEtat("running");
    setSuivi(null);
    setRes(null);
    setErreur(null);
    try {
      const t = await demarrer();
      setSuivi(t);
      setTaskId(t.task_id);
      ecrireCle(memoriser, t.task_id);
    } catch (e) {
      setErreur(messageErreur(e));
      setEtat("error");
    }
  }, [memoriser]);

  const reinitialiser = useCallback(() => {
    ecrireCle(memoriser, null);
    setEtat("idle"); setSuivi(null); setRes(null); setErreur(null); setTaskId(null);
  }, [memoriser]);

  return { etat, suivi, resultat: res, erreur, lancer, reinitialiser };
}
