type Props = { count: number; max?: number };

export function Badge({ count, max = 99 }: Props) {
  if (count <= 0) {
    return null;
  }
  const label = count > max ? `${max}+` : String(count);
  return <span className="badge">{label}</span>;
}
