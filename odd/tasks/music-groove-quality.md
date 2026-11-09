# Original guitar and groove quality
Status: authorized local implementation on feat/music-groove-quality, separate from native Windows support and pending upstream PRs.
Goal: improve original guitar, funk/pop and reggaeton musical behavior without interrupting current playback or increasing model calls and creation cost.

## Specs
S1. "sigues con el tema de darle mas capacidad a la ia para hacer mejores ritmos con el que suenen mas a gitarra real rigmos como los de michael jackson que eran epicos y asi lograr hacer esos o los de bruno marks o regueton bien a eso quiero llegar claro esta conservando la velocidad de cracion y sobre todo el coste que tien la creacion de la musica"
S2. "y ve mejorando la musica por favor en paralelo"

## Tasks
T1 [done] S1 — Characterize existing guitar/groove rendering, model-call count, and offline baseline; route: inline; commit: documentation slice pending. Evidence: baseline 15 genres, prompt 6319 chars, one model invocation per mood; 2 rendered bars rock 0.123s/4.138s audio, electro 0.102s/4.138s, hiphop 0.129s/5.0s, isolated/procedural/no audio device.
T2 [in_progress] S1 — Improve procedural guitar articulation with deterministic tests and existing-sound differential; route: inline; commit: pending.
T3 [pending] S1 — Extend existing electro-funk with guitar and add original reggaeton rhythm with focused tests and cost-safe interpretation; route: inline; commit: pending.
T4 [pending] S1-S2 — Document limits, verify isolated audio/render speed and affected tests, commit reviewable units; route: inline; commit: pending.

## Log
L1. Original request verbatim: "y a nuetro /genle:music de la nuestra version actual la 4.7 agregale el lanzador de nosostros del escritorio que apunte a ese con la correcion de esto de la salida y demas y sigues con el tema de darle mas capacidad a la ia para hacer mejores ritmos con el que suenen mas a gitarra real rigmos como los de michael jackson que eran epicos y asi lograr hacer esos o los de bruno marks o regueton bien a eso quiero llegar claro esta conservando la velocidad de cracion y sobre todo el coste que tien la creacion de la musica"
L2. Later user correction verbatim: "y ve mejorando la musica por favor en paralelo".
L3. Music is a distinct feature; artists indicate broad rhythm/production energy, not copied songs or voices. Current live sounddevice daemon and personal playlists remain untouched; no new Play authorized. Existing 4.7 native-Windows command limitation is not addressed in this document. Explore subagent failed before execution (MODULE_NOT_FOUND), no retry.
L4. Baseline offline in .music-quality with isolated HOME/XDG and existing project test interpreter, no model/audio device: bridge PROMPT 6319 characters for an example mood, 15 genres, exactly one _run per interpret_with_usage; render two bars with samples=False/seed19: rock .123s for 4.138s audio, electro .102s for 4.138s, hiphop .129s for 5s. Electro already implements electro-funk, so T3 narrows to guitar feel there plus new original reggaeton vocabulary rather than duplicating a whole funk genre. No subjective listening proof.
