export default function Card({ children, className = '', padded = true, ...props }) {
  return (
    <div
      className={`card-base ${padded ? 'p-6' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, action, className = '' }) {
  return (
    <div className={`flex items-center justify-between ${className}`}>
      <h3 className="section-title">{title}</h3>
      {action}
    </div>
  );
}

export function StructuredCard({ title, children, className = '', action }) {
  return (
    <div className={`card-base overflow-hidden ${className}`}>
      <div className="px-6 pt-6">
        <CardHeader title={title} action={action} className="mb-4" />
      </div>
      <div className="mx-6 border-t border-gray-100" />
      <div className="p-6 pt-4">{children}</div>
    </div>
  );
}