export default function LoadingSpinner({ size = 'md', text = null, className = '' }) {
  const sizes = {
    sm: 'h-5 w-5',
    md: 'h-10 w-10',
    lg: 'h-14 w-14',
  };

  return (
    <div className={`text-center ${className}`}>
      <div
        className={`animate-spin rounded-full border-2 border-gray-200 border-t-blue-600 mx-auto mb-3 ${sizes[size]}`}
      />
      {text && <p className="text-sm text-gray-600">{text}</p>}
    </div>
  );
}