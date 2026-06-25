const VARIANTS = {
  primary:
    'text-white bg-indigo-600 hover:bg-indigo-700 border-transparent focus:ring-indigo-500',
  secondary:
    'text-gray-700 bg-white hover:bg-gray-50 border-gray-200 focus:ring-indigo-500',
  danger:
    'text-white bg-red-600 hover:bg-red-700 border-transparent focus:ring-red-500',
  dark:
    'text-white bg-gray-900 hover:bg-gray-800 border-transparent focus:ring-gray-500',
};

export default function Button({
  children,
  variant = 'primary',
  className = '',
  disabled = false,
  type = 'button',
  onClick,
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`
        inline-flex items-center justify-center gap-2
        h-9 px-3.5 text-sm font-medium
        border rounded-lg
        transition-colors duration-150
        focus:outline-none focus:ring-2 focus:ring-offset-2
        disabled:opacity-50 disabled:cursor-not-allowed
        ${VARIANTS[variant] || VARIANTS.primary}
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
}