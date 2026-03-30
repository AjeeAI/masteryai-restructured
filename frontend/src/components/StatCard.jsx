export default function StatCard({ 
  icon: Icon, 
  title, 
  value, 
  subtext, 
  subtextColor = "text-gray-500", 
  iconBg = "bg-gray-50", 
  iconColor = "text-gray-500" 
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3.5 shadow-sm">
      <div className={`flex h-10 w-10 items-center justify-center rounded-2xl ${iconBg}`}>
        <Icon className={`h-4.5 w-4.5 ${iconColor}`} />
      </div>
      <div>
        <p className="mb-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">{title}</p>
        <div className="text-[1.55rem] font-black leading-none text-slate-900 sm:text-[1.7rem]">{value}</div>
        {subtext && <p className={`mt-1 text-xs font-medium ${subtextColor}`}>{subtext}</p>}
      </div>
    </div>
  );
}
