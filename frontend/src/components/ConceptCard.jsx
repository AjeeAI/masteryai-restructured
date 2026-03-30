export default function ConceptCard({ title, mastery, description }) {
  const isHighMastery = mastery >= 80;
  const barColor = isHighMastery ? 'bg-emerald-500' : 'bg-orange-500';
  const textColor = isHighMastery ? 'text-emerald-500' : 'text-orange-500';

  return (
    <div className="bg-[#1c2438] rounded-xl p-5 border border-slate-700">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-white font-bold">{title}</h3>
        <span className={`text-sm font-bold ${textColor}`}>{mastery}% Mastery</span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-2 mb-4">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${mastery}%` }}></div>
      </div>
      <p className="text-slate-400 text-xs leading-relaxed">
        {description}
      </p>
    </div>
  );
}