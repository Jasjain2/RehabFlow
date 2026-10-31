interface Props {
  onStop: () => void;
  stopping: boolean;
}

/** Always visible during exercise. One tap ends the session: no confirmation, because
 * someone in pain mid-rep needs one tap, not two. */
export default function EmergencyStop({ onStop, stopping }: Props) {
  return (
    <button
      onClick={onStop}
      disabled={stopping}
      aria-label="Emergency stop: end the session now"
      className="fixed bottom-[calc(1.5rem+env(safe-area-inset-bottom,0px))] right-6 z-50 flex h-24 w-24 flex-col items-center justify-center rounded-full bg-red-600 text-white shadow-lg ring-4 ring-red-200 hover:bg-red-700 focus:outline-none focus:ring-red-400 disabled:bg-red-400"
    >
      <span className="text-2xl leading-none">■</span>
      <span className="mt-1 text-sm font-bold uppercase tracking-wide">{stopping ? 'Saving' : 'Stop'}</span>
    </button>
  );
}
