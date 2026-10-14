const db = require('./server/db.js');

// Drop and recreate the table with correct schema
db.exec('DROP TABLE IF EXISTS Insurance_Providers;');

db.exec(`
  CREATE TABLE Insurance_Providers (
      ProviderId   TEXT PRIMARY KEY,
      ProviderName VARCHAR(100) NOT NULL,
      LogoUrl      VARCHAR(255),
      Website      VARCHAR(255)
  );
`);

console.log('Recreated Insurance_Providers table with TEXT ProviderId');

// Verify the change
const tableInfo = db.prepare('PRAGMA table_info(Insurance_Providers)').all();
console.log('Table structure:');
console.log(JSON.stringify(tableInfo, null, 2));

// Insert the 4 insurance providers from the mock data
const providers = [
  { ProviderId: 'tawuniya', ProviderName: 'التعاونية للتأمين' },
  { ProviderId: 'rajhi', ProviderName: 'الراجحي تكافل' },
  { ProviderId: 'medgulf', ProviderName: 'ميدغلف للتأمين' },
  { ProviderId: 'acig', ProviderName: 'المجموعة المتحدة للتأمين (ACIG)' }
];

const insertStmt = db.prepare('INSERT OR IGNORE INTO Insurance_Providers (ProviderId, ProviderName) VALUES (?, ?)');

providers.forEach(provider => {
  const info = insertStmt.run(provider.ProviderId, provider.ProviderName);
  console.log(`Inserted provider ${provider.ProviderName}: ${info.changes} row(s) affected`);
});

// Verify insertion
const allProviders = db.prepare('SELECT ProviderId, ProviderName FROM Insurance_Providers ORDER BY ProviderId').all();
console.log('\\nAll providers in database:');
console.log(JSON.stringify(allProviders, null, 2));