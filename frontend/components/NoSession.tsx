import Link from 'next/link';

export default function NoSession() {
  return (
    <div className="mx-auto max-w-md rounded-lg border border-slate-200 bg-white p-6 text-center">
      <p className="text-slate-700">No active session found.</p>
      <Link href="/" className="mt-4 inline-block font-medium text-teal-700 hover:underline">
        Start a new session
      </Link>
    </div>
  );
}
