type Props = { count: number };

export function Badge({ count }: Props) {
  return <span className="badge">{count}</span>;
}
