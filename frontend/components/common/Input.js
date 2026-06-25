export default function Input({
  label,
  error,
  helperText,
  className = '',
  ...props
}) {
  return (
    <div>
      {label && (
        <label className="block mb-1.5 text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <input
        className={`
          input-base
          disabled:bg-gray-100 disabled:text-gray-500
          ${error ? 'border-red-300 focus:ring-red-500' : ''}
          ${className}
        `}
        {...props}
      />
      {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
      {helperText && !error && (
        <p className="mt-1.5 text-xs text-gray-400">{helperText}</p>
      )}
    </div>
  );
}