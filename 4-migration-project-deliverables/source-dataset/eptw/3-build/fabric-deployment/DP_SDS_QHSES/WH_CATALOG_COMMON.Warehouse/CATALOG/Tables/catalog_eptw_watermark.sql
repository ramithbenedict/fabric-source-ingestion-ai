CREATE TABLE [CATALOG].[catalog_eptw_watermark] (

	[SchemaName] varchar(50) NOT NULL, 
	[TableName] varchar(200) NOT NULL, 
	[WatermarkVal] datetime2(6) NULL, 
	[UpdatedAt] datetime2(6) NULL
);